#!/usr/bin/env python3
"""TickFlow-based full sync — batch pull + bulk insert to PostgreSQL.

Key: uses multi-row INSERT (500 rows/statement) for speed.
Usage: python3 sync_tickflow.py
"""

import logging
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from tickflow import TickFlow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("sync_tickflow")

DB_URL = "postgresql://postgres:postgres@localhost:5432/stock_backtest"
STOCKS_PER_BATCH = 100    # Stocks per TickFlow API call
ROWS_PER_INSERT = 500     # Rows per multi-row INSERT
FAIL_LOG = "/tmp/tickflow_failed.txt"

INSERT_SQL = """INSERT INTO stock_daily
(code, trade_date, open, high, low, close, volume, amount)
VALUES {values_clause}
ON CONFLICT (code, trade_date) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high,
    low = EXCLUDED.low, close = EXCLUDED.close,
    volume = EXCLUDED.volume, amount = EXCLUDED.amount"""


def bulk_insert(conn, rows: list[dict]):
    """Insert rows in chunks using multi-row INSERT."""
    for i in range(0, len(rows), ROWS_PER_INSERT):
        chunk = rows[i : i + ROWS_PER_INSERT]
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
        sql = INSERT_SQL.format(values_clause=", ".join(placeholders))
        conn.execute(text(sql), params)


def main():
    engine = create_engine(DB_URL, echo=False)

    # ── Step 1: Get codes to fetch ──
    with engine.connect() as conn:
        all_codes = [
            row[0]
            for row in conn.execute(
                text("SELECT code FROM stock_basic WHERE status = 1 ORDER BY code")
            ).fetchall()
        ]
        existing = set(
            row[0]
            for row in conn.execute(
                text("SELECT DISTINCT code FROM stock_daily")
            ).fetchall()
        )
    codes_to_fetch = [c for c in all_codes if c not in existing]
    logger.info(
        f"Total: {len(all_codes)}, already done: {len(existing)}, to fetch: {len(codes_to_fetch)}"
    )

    if not codes_to_fetch:
        logger.info("Nothing to fetch!")
        return

    # ── Step 2: Init TickFlow ──
    tf = TickFlow.free()
    total_rows = 0
    failed_codes = []
    batches = [
        codes_to_fetch[i : i + STOCKS_PER_BATCH]
        for i in range(0, len(codes_to_fetch), STOCKS_PER_BATCH)
    ]
    logger.info(f"Processing {len(batches)} batches of up to {STOCKS_PER_BATCH} stocks each")

    # ── Step 3: Batch fetch + bulk insert ──
    for bi, batch in enumerate(batches):
        batch_start = time.time()
        logger.info(
            f"[batch {bi + 1}/{len(batches)}] Fetching {len(batch)} stocks..."
        )

        # Fetch
        try:
            dfs = tf.klines.batch(
                batch,
                period="1d",
                count=10000,
                as_dataframe=True,
                show_progress=False,
            )
        except Exception as e:
            logger.error(f"Batch {bi+1} fetch failed: {e}")
            failed_codes.extend(batch)
            continue

        # Collect rows
        insert_rows = []
        batch_failed = 0
        for sym in batch:
            df = dfs.get(sym)
            if df is None or df.empty:
                batch_failed += 1
                failed_codes.append(sym)
                continue
            for _, row in df.iterrows():
                td = str(row.get("trade_date", ""))[:10]
                if not td:
                    continue
                insert_rows.append({
                    "code": sym,
                    "td": td,
                    "o": float(row.get("open", 0) or 0),
                    "h": float(row.get("high", 0) or 0),
                    "l": float(row.get("low", 0) or 0),
                    "c": float(row.get("close", 0) or 0),
                    "v": float(row.get("volume", 0) or 0),
                    "a": float(row.get("amount", 0) or 0),
                })

        # Bulk insert
        with engine.begin() as conn:
            bulk_insert(conn, insert_rows)

        elapsed = time.time() - batch_start
        progress_pct = (bi + 1) / len(batches) * 100
        total_rows += len(insert_rows)
        logger.info(
            f"  OK: {len(batch) - batch_failed} stocks, "
            f"{len(insert_rows)} rows in {elapsed:.1f}s "
            f"({progress_pct:.0f}% done, {total_rows} total rows)"
        )

    # ── Step 4: Save failed codes ──
    if failed_codes:
        with open(FAIL_LOG, "w") as f:
            f.write("\n".join(failed_codes))
        logger.info(f"Failed codes saved to {FAIL_LOG}: {len(failed_codes)} stocks")

    # ── Step 5: Generate trade calendar ──
    logger.info("Generating trade calendar...")
    with engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO trade_calendar (trade_date, is_trade_day)
                SELECT DISTINCT trade_date, true FROM stock_daily
                ON CONFLICT (trade_date) DO NOTHING"""
            )
        )
        conn.execute(
            text(
                """UPDATE trade_calendar tc SET
                pre_trade_date = (
                    SELECT trade_date FROM trade_calendar
                    WHERE trade_date < tc.trade_date ORDER BY trade_date DESC LIMIT 1
                ),
                next_trade_date = (
                    SELECT trade_date FROM trade_calendar
                    WHERE trade_date > tc.trade_date ORDER BY trade_date ASC LIMIT 1
                )"""
            )
        )

    # ── Step 6: Verify ──
    with engine.connect() as conn:
        sc = conn.execute(text("SELECT COUNT(*) FROM stock_basic")).scalar()
        dc = conn.execute(text("SELECT COUNT(*) FROM stock_daily")).scalar()
        cc = conn.execute(text("SELECT COUNT(*) FROM trade_calendar")).scalar()
        dc_codes = conn.execute(
            text("SELECT COUNT(DISTINCT code) FROM stock_daily")
        ).scalar()
        logger.info(
            f"\n=== FINAL ==="
            f"\n  Stocks: {sc} basic, {dc_codes} with daily data"
            f"\n  Daily rows: {dc}"
            f"\n  Trade days: {cc}"
            f"\n  Failed: {len(failed_codes)}"
        )


if __name__ == "__main__":
    main()
