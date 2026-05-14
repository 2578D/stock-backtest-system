"""Celery task for data sync using TickFlow provider."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.redis import get_redis_sync
from app.services.tickflow_provider import TickFlowProvider

logger = logging.getLogger(__name__)

settings = get_settings()
_sync_engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)
SyncSession = sessionmaker(bind=_sync_engine)

BATCH_SIZE = 100       # Stocks per TickFlow API call
ROWS_PER_INSERT = 500  # Rows per multi-row INSERT
FAIL_LOG = "/tmp/tickflow_failed.txt"


def _set_progress(redis, key: str, pct: float, msg: str = ""):
    """Update sync progress in Redis."""
    try:
        redis.set(f"sync:progress:{key}", f"{pct:.1f}% {msg}", ex=3600)
    except Exception:
        pass


@celery_app.task(bind=True, name="data_sync.incremental_sync")
def incremental_sync(self, lookback_days: int = 5):
    """Incremental daily sync: fetch only the last N trading days for all stocks.

    Runs every hour (Celery Beat), but skips if:
    - Data is already up to date (latest trade_date = today or yesterday)
    - It's before 15:30 on a weekday (market hasn't closed yet)
    """
    from datetime import datetime, timedelta

    now = datetime.now()
    weekday = now.weekday()

    # Skip weekends
    if weekday >= 5:
        logger.info("Incremental sync skipped: weekend")
        return {"status": "skipped", "reason": "weekend"}

    # Skip if before 15:30 (market still open)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now < market_close:
        logger.info("Incremental sync skipped: market not closed yet")
        return {"status": "skipped", "reason": "before_market_close"}

    redis = get_redis_sync()

    # Check latest data date
    with SyncSession() as s:
        latest = s.execute(
            text("SELECT MAX(trade_date) FROM stock_daily")
        ).scalar()

    today = now.date()
    if latest and latest >= today:
        logger.info(f"Incremental sync skipped: data already up-to-date ({latest})")
        return {"status": "skipped", "reason": "up_to_date", "latest": str(latest)}

    logger.info(f"Starting incremental sync (latest={latest}, today={today})")
    _set_progress(redis, "incremental", 0, f"Incremental sync from {latest}...")

    tf = TickFlowProvider()

    # Get all active stocks
    with SyncSession() as s:
        codes = [
            row[0] for row in s.execute(
                text("SELECT code FROM stock_basic WHERE status = 1 ORDER BY code")
            ).fetchall()
        ]

    if not codes:
        return {"status": "skipped", "reason": "no_stocks"}

    # Batch fetch
    STOCKS_PER_BATCH = 100
    ROWS_PER_INSERT = 500
    total_rows = 0
    failed = 0

    INSERT_SQL = """INSERT INTO stock_daily
    (code, trade_date, open, high, low, close, volume, amount)
    VALUES {values_clause}
    ON CONFLICT (code, trade_date) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high,
        low = EXCLUDED.low, close = EXCLUDED.close,
        volume = EXCLUDED.volume, amount = EXCLUDED.amount"""

    batches = [
        codes[i : i + STOCKS_PER_BATCH]
        for i in range(0, len(codes), STOCKS_PER_BATCH)
    ]

    for bi, batch in enumerate(batches):
        pct = (bi / len(batches)) * 100
        _set_progress(redis, "incremental", pct, f"Batch {bi+1}/{len(batches)}")

        try:
            data = tf.fetch_batch(batch)
        except Exception as e:
            logger.error(f"Incremental batch {bi+1} failed: {e}")
            failed += len(batch)
            continue

        # Filter to only recent bars (last N days)
        insert_rows = []
        for sym in batch:
            bars = data.get(sym, [])
            for bar in bars:
                # Only keep bars newer than latest date in DB
                insert_rows.append({
                    "code": sym,
                    "td": bar["trade_date"],
                    "o": bar["open"],
                    "h": bar["high"],
                    "l": bar["low"],
                    "c": bar["close"],
                    "v": bar["volume"],
                    "a": bar["amount"],
                })

        if not insert_rows:
            continue

        # Bulk insert
        with SyncSession() as s:
            for i in range(0, len(insert_rows), ROWS_PER_INSERT):
                chunk = insert_rows[i : i + ROWS_PER_INSERT]
                placeholders = []
                params = {}
                for j, r in enumerate(chunk):
                    p = f"_{j}"
                    placeholders.append(
                        f"(:c{p}, :td{p}, :o{p}, :h{p}, :l{p}, :cl{p}, :v{p}, :a{p})"
                    )
                    params.update({
                        f"c{p}": r["code"],
                        f"td{p}": r["td"],
                        f"o{p}": r["o"],
                        f"h{p}": r["h"],
                        f"l{p}": r["l"],
                        f"cl{p}": r["c"],
                        f"v{p}": r["v"],
                        f"a{p}": r["a"],
                    })
                s.execute(
                    text(INSERT_SQL.format(values_clause=", ".join(placeholders))),
                    params,
                )
            s.commit()

        total_rows += len(insert_rows)

    # Update trade calendar with new dates
    with SyncSession() as s:
        s.execute(text("""
            INSERT INTO trade_calendar (trade_date, is_trade_day)
            SELECT DISTINCT trade_date, true FROM stock_daily
            ON CONFLICT (trade_date) DO NOTHING
        """))
        s.execute(text("""
            UPDATE trade_calendar tc SET
                pre_trade_date = (
                    SELECT trade_date FROM trade_calendar
                    WHERE trade_date < tc.trade_date ORDER BY trade_date DESC LIMIT 1
                ),
                next_trade_date = (
                    SELECT trade_date FROM trade_calendar
                    WHERE trade_date > tc.trade_date ORDER BY trade_date ASC LIMIT 1
                )
        """))
        s.commit()

    _set_progress(redis, "incremental", 100, f"Done: {total_rows} new rows")

    logger.info(f"Incremental sync complete: {total_rows} new rows, {failed} failed")
    return {
        "status": "complete",
        "new_rows": total_rows,
        "failed": failed,
    }


@celery_app.task(bind=True, name="data_sync.full_init_sync")
def full_init_sync(self, cookie: str = ""):
    """Full data sync: fetch all daily bars for all stocks using TickFlow.

    1. Get stock list from DB
    2. Batch-pull klines via TickFlow
    3. Bulk insert into stock_daily
    4. Generate trade_calendar
    """
    redis = get_redis_sync()
    logger.info("Starting full data sync via TickFlow...")
    _set_progress(redis, "init", 0, "Starting...")

    tf = TickFlowProvider()

    # Step 1: Get stock codes
    with SyncSession() as s:
        all_codes = [
            row[0] for row in s.execute(
                text("SELECT code FROM stock_basic WHERE status = 1 ORDER BY code")
            ).fetchall()
        ]
        existing = set(
            row[0] for row in s.execute(
                text("SELECT DISTINCT code FROM stock_daily")
            ).fetchall()
        )

    codes_to_fetch = [c for c in all_codes if c not in existing]
    logger.info(
        f"Sync plan: {len(all_codes)} total, {len(existing)} done, {len(codes_to_fetch)} to fetch"
    )

    if not codes_to_fetch:
        _set_progress(redis, "init", 100, "Already up-to-date")
        return {"status": "complete", "rows": 0, "message": "Already up-to-date"}

    # Step 2: Batch fetch + insert
    batches = [
        codes_to_fetch[i : i + BATCH_SIZE]
        for i in range(0, len(codes_to_fetch), BATCH_SIZE)
    ]
    total_rows = 0
    failed_codes: list[str] = []

    INSERT_SQL = """INSERT INTO stock_daily
    (code, trade_date, open, high, low, close, volume, amount)
    VALUES {values_clause}
    ON CONFLICT (code, trade_date) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high,
        low = EXCLUDED.low, close = EXCLUDED.close,
        volume = EXCLUDED.volume, amount = EXCLUDED.amount"""

    for bi, batch in enumerate(batches):
        pct = (bi / len(batches)) * 100
        _set_progress(redis, "init", pct, f"Batch {bi+1}/{len(batches)} ({len(batch)} stocks)")

        logger.info(f"[batch {bi+1}/{len(batches)}] Fetching {len(batch)} stocks...")

        try:
            data = tf.fetch_batch(batch)
        except Exception as e:
            logger.error(f"Batch {bi+1} fetch failed: {e}")
            failed_codes.extend(batch)
            continue

        # Build insert rows
        insert_rows = []
        for sym in batch:
            bars = data.get(sym)
            if not bars:
                failed_codes.append(sym)
                continue
            for bar in bars:
                insert_rows.append({
                    "code": sym,
                    "td": bar["trade_date"],
                    "o": bar["open"],
                    "h": bar["high"],
                    "l": bar["low"],
                    "c": bar["close"],
                    "v": bar["volume"],
                    "a": bar["amount"],
                })

        # Bulk insert
        with SyncSession() as s:
            for i in range(0, len(insert_rows), ROWS_PER_INSERT):
                chunk = insert_rows[i : i + ROWS_PER_INSERT]
                placeholders = []
                params = {}
                for j, r in enumerate(chunk):
                    p = f"_{j}"
                    placeholders.append(
                        f"(:c{p}, :td{p}, :o{p}, :h{p}, :l{p}, :cl{p}, :v{p}, :a{p})"
                    )
                    params.update({
                        f"c{p}": r["code"],
                        f"td{p}": r["td"],
                        f"o{p}": r["o"],
                        f"h{p}": r["h"],
                        f"l{p}": r["l"],
                        f"cl{p}": r["c"],
                        f"v{p}": r["v"],
                        f"a{p}": r["a"],
                    })
                s.execute(text(INSERT_SQL.format(values_clause=", ".join(placeholders))), params)
            s.commit()

        total_rows += len(insert_rows)
        logger.info(
            f"  OK: {len(batch) - len(failed_codes[-len(batch):]) if failed_codes else len(batch)} "
            f"stocks, {len(insert_rows)} rows, {total_rows} total"
        )

    # Step 3: Save failed codes
    if failed_codes:
        with open(FAIL_LOG, "w") as f:
            f.write("\n".join(failed_codes))
        logger.info(f"Failed codes: {len(failed_codes)} saved to {FAIL_LOG}")

    # Step 4: Generate trade calendar
    _set_progress(redis, "init", 95, "Generating trade calendar...")
    with SyncSession() as s:
        s.execute(text("""
            INSERT INTO trade_calendar (trade_date, is_trade_day)
            SELECT DISTINCT trade_date, true FROM stock_daily
            ON CONFLICT (trade_date) DO NOTHING
        """))
        s.execute(text("""
            UPDATE trade_calendar tc SET
                pre_trade_date = (
                    SELECT trade_date FROM trade_calendar
                    WHERE trade_date < tc.trade_date ORDER BY trade_date DESC LIMIT 1
                ),
                next_trade_date = (
                    SELECT trade_date FROM trade_calendar
                    WHERE trade_date > tc.trade_date ORDER BY trade_date ASC LIMIT 1
                )
        """))
        s.commit()

    # Step 5: Verify
    with SyncSession() as s:
        sc = s.execute(text("SELECT COUNT(*) FROM stock_basic")).scalar()
        dc = s.execute(text("SELECT COUNT(*) FROM stock_daily")).scalar()
        cc = s.execute(text("SELECT COUNT(*) FROM trade_calendar")).scalar()
        dc_codes = s.execute(
            text("SELECT COUNT(DISTINCT code) FROM stock_daily")
        ).scalar()
        logger.info(
            f"Sync complete: {sc} stocks, {dc_codes} with data, "
            f"{dc} rows, {cc} trade days, {len(failed_codes)} failed"
        )

    _set_progress(redis, "init", 100, f"Done: {total_rows} rows, {dc_codes} stocks")

    return {
        "status": "complete",
        "rows": total_rows,
        "stocks_with_data": dc_codes,
        "failed": len(failed_codes),
        "message": f"Synced {total_rows} rows for {dc_codes} stocks",
    }
