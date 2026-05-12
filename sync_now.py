#!/usr/bin/env python3
"""Standalone full sync script — bypasses Celery for direct execution.

Usage: python3 sync_now.py [--cookie "ct=..."]
"""

import asyncio
import logging
import os
import sys
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sync_now")

COOKIE = os.environ.get(
    "EFINANCE_COOKIE",
    "ct=l14pdoBvQf78uI1kxOd3XBfHt1_YM0x4mRj_7U97ysvJyr7XGNIrqezIi_vvZkhfZn1qYnvdtM4mPM0dx7qEOg1aLrmswthhlwV8mQ0baVQI7eleacgUSp2VH1SuQ8SKxmAQeYzq4Bog_ofgKC25GLXs1TQZ4bVIJG5bR9Tt70o",
)

# Patch efinance's requests session to use Keep-Alive and fewer retries
# This reduces connection churn and speeds up recovery from rate limits
def _patch_efinance_session():
    """Configure efinance to reuse connections and be less aggressive with retries."""
    import efinance.common.config as cfg

    # Create a persistent session with retry config
    session = requests.Session()
    retry_strategy = Retry(
        total=2,  # Only 2 retries (down from default 5)
        backoff_factor=1.0,  # 1s, 2s backoff
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=retry_strategy,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Store the session so efinance can use it
    cfg._PATCHED_SESSION = session
    return session


def _patch_efinance_getter():
    """Monkey-patch efinance's getter to use our persistent session."""
    import efinance.common.getter as getter
    import efinance.futures.getter as fgetter

    session = _patch_efinance_session()

    # Patch the _get_with_session or equivalent function
    # efinance uses requests.get(url, headers=..., params=..., verify=False)
    # We need to replace those calls
    orig_requests_get = requests.get

    def patched_get(url, **kwargs):
        kwargs.setdefault("timeout", 15)
        kwargs.setdefault("verify", False)
        return session.get(url, **kwargs)

    requests.get = patched_get
    return orig_requests_get


async def main():
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    # Use sync SQLAlchemy for simplicity
    engine = create_engine(
        "postgresql://postgres:postgres@localhost:5432/stock_backtest",
        echo=False,
    )
    Session = sessionmaker(bind=engine)

    # Step 1: Inject cookie and get stock list
    logger.info("=== Step 1: Injecting cookie + fetching stock list ===")
    from app.services.efinance_provider import EfinanceProvider

    provider = EfinanceProvider(cookie=COOKIE)

    # Get all stocks
    logger.info("Fetching stock list from efinance (this may take 10-30s)...")
    try:
        df_stocks = provider.get_instruments()
        logger.info(f"Got {len(df_stocks)} stocks")

        # Save first batch of columns for inspection
        logger.info(f"Columns: {list(df_stocks.columns[:20])}")
        if len(df_stocks) > 0:
            logger.info(f"Sample: {df_stocks.iloc[0].to_dict()}")
    except Exception as e:
        logger.error(f"Failed to get stock list: {e}")
        logger.info("Trying fallback: fetching a few known stocks directly...")
        # Fallback: manually create a small stock list
        import pandas as pd
        df_stocks = pd.DataFrame({
            "code": ["600519.SH", "000001.SZ", "600036.SH", "000858.SZ", "601318.SH"],
            "name": ["贵州茅台", "平安银行", "招商银行", "五粮液", "中国平安"],
            "exchange": ["SH", "SZ", "SH", "SZ", "SH"],
        })
        logger.info(f"Using fallback list with {len(df_stocks)} stocks")

    # Step 2: Save stock basic info to DB
    logger.info("\n=== Step 2: Saving stock basic info ===")
    with Session() as session:
        for _, row in df_stocks.iterrows():
            try:
                code = str(row.get("code", "")).strip()
                name = str(row.get("name", ""))
                exchange = str(row.get("exchange", "SH"))
                session.execute(
                    text("""
                        INSERT INTO stock_basic (code, name, exchange, status)
                        VALUES (:code, :name, :exchange, 1)
                        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
                    """),
                    {"code": code, "name": name, "exchange": exchange}
                )
            except Exception as e:
                logger.warning(f"Failed to upsert {row.get('code', '?')}: {e}")
        session.commit()
    logger.info(f"Saved {len(df_stocks)} stocks to stock_basic")

    # Step 3: Fetch daily bars — fresh-connection-per-request strategy
    # EastMoney actively closes reused connections → NO Keep-Alive, fresh each time
    logger.info("\n=== Step 3: Fetching daily bars (fresh-connection mode) ===")
    # Do NOT patch efinance — let each call use a brand-new requests.get()

    import random as _random

    # ── Conservative rate-limit params ──
    BATCH_SIZE = 20       # Small batch
    DELAY_MIN = 8.0        # Min seconds between stocks
    DELAY_MAX = 14.0       # Max seconds (random jitter)
    BATCH_PAUSE = 60       # 60s pause every batch
    ERROR_COOLDOWN = 120   # 2min cooldown after connection errors

    # ── Skip already-fetched codes ──
    with Session() as session:
        existing = session.execute(
            text("SELECT DISTINCT code FROM stock_daily")
        ).fetchall()
        existing_codes = set(row[0] for row in existing)
    logger.info(f"{len(existing_codes)} codes already have daily data, will skip")

    all_codes = list(df_stocks["code"])
    codes_to_fetch = [c for c in all_codes if c not in existing_codes]
    already = len(all_codes) - len(codes_to_fetch)
    logger.info(f"Total: {len(all_codes)}, already done: {already}, to fetch: {len(codes_to_fetch)}")

    total_rows = 0
    failed_codes = []
    error_streak = 0  # Track consecutive errors for adaptive backoff

    for i, code in enumerate(codes_to_fetch):
        raw_code = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        logger.info(f"[{i+1}/{len(codes_to_fetch)}] Fetching {raw_code}...")

        try:
            df_bars = provider.get_daily_bars(code)
            if df_bars is None or df_bars.empty:
                logger.warning(f"  No data for {raw_code}, skipping")
                continue

            logger.info(f"  Got {len(df_bars)} bars ({df_bars.iloc[0].get('trade_date', '?')} ~ {df_bars.iloc[-1].get('trade_date', '?')})")

            # Batch insert
            with Session() as session:
                for _, row in df_bars.iterrows():
                    try:
                        vals = {
                            "code": code,
                            "trade_date": str(row.get("trade_date", ""))[:10],
                            "open": float(row.get("open", 0) or 0),
                            "high": float(row.get("high", 0) or 0),
                            "low": float(row.get("low", 0) or 0),
                            "close": float(row.get("close", 0) or 0),
                            "volume": float(row.get("volume", 0) or 0),
                            "amount": float(row.get("amount", 0) or 0),
                        }
                        session.execute(
                            text("""
                                INSERT INTO stock_daily (code, trade_date, open, high, low, close, volume, amount)
                                VALUES (:code, :trade_date, :open, :high, :low, :close, :volume, :amount)
                                ON CONFLICT (code, trade_date) DO UPDATE SET
                                    open = EXCLUDED.open, high = EXCLUDED.high,
                                    low = EXCLUDED.low, close = EXCLUDED.close,
                                    volume = EXCLUDED.volume, amount = EXCLUDED.amount
                            """),
                            vals,
                        )
                    except Exception as e:
                        logger.warning(f"  Failed row {row.get('trade_date')}: {e}")
                session.commit()

            total_rows += len(df_bars)
            error_streak = 0  # Reset on success

        except Exception as e:
            logger.error(f"  Failed to fetch {raw_code}: {e}")
            error_streak += 1
            failed_codes.append(code)
            # After consecutive errors, take a longer break
            if error_streak >= 3:
                logger.warning(f"  {error_streak} consecutive errors, cooling down {ERROR_COOLDOWN}s...")
                time.sleep(ERROR_COOLDOWN)
                error_streak = 0

        # Randomised pause between stocks
        delay = _random.uniform(DELAY_MIN, DELAY_MAX)
        time.sleep(delay)

        # Batch pause to avoid rate limiting
        if (i + 1) % BATCH_SIZE == 0:
            done_pct = (i + 1) / len(codes_to_fetch) * 100
            logger.info(
                f"--- Batch pause: {i+1}/{len(codes_to_fetch)} ({done_pct:.1f}%) done, "
                f"sleeping {BATCH_PAUSE}s ---"
            )
            time.sleep(BATCH_PAUSE)

    logger.info(f"\n=== First pass done! Total rows inserted: {total_rows}, failed: {len(failed_codes)} ===")

    # Step 3b: Retry failed codes with longer delays
    if failed_codes:
        logger.info(f"\n=== Retrying {len(failed_codes)} failed codes ===")
        retry_success = 0
        for i, code in enumerate(failed_codes):
            raw_code = code.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
            logger.info(f"[retry {i+1}/{len(failed_codes)}] {raw_code}...")
            try:
                df_bars = provider.get_daily_bars(code)
                if df_bars is not None and not df_bars.empty:
                    with Session() as session:
                        for _, row in df_bars.iterrows():
                            try:
                                vals = {
                                    "code": code,
                                    "trade_date": str(row.get("trade_date", ""))[:10],
                                    "open": float(row.get("open", 0) or 0),
                                    "high": float(row.get("high", 0) or 0),
                                    "low": float(row.get("low", 0) or 0),
                                    "close": float(row.get("close", 0) or 0),
                                    "volume": float(row.get("volume", 0) or 0),
                                    "amount": float(row.get("amount", 0) or 0),
                                }
                                session.execute(
                                    text("""
                                        INSERT INTO stock_daily (code, trade_date, open, high, low, close, volume, amount)
                                        VALUES (:code, :trade_date, :open, :high, :low, :close, :volume, :amount)
                                        ON CONFLICT (code, trade_date) DO UPDATE SET
                                            open = EXCLUDED.open, high = EXCLUDED.high,
                                            low = EXCLUDED.low, close = EXCLUDED.close,
                                            volume = EXCLUDED.volume, amount = EXCLUDED.amount
                                    """), vals)
                            except Exception as e:
                                logger.warning(f"  Failed row: {e}")
                        session.commit()
                    total_rows += len(df_bars)
                    retry_success += 1
                    logger.info(f"  OK ({len(df_bars)} bars)")
                else:
                    logger.warning(f"  Still no data")
            except Exception as e:
                logger.error(f"  Still failed: {e}")
            # 15-30s between retries
            time.sleep(_random.uniform(15, 30))
        logger.info(f"Retry done: {retry_success}/{len(failed_codes)} recovered")

    logger.info(f"\n=== Done! Total rows inserted: {total_rows} ===")

    # Step 4: Generate trade calendar
    logger.info("Generating trade calendar...")
    with Session() as session:
        session.execute(text("""
            INSERT INTO trade_calendar (trade_date, is_trade_day)
            SELECT DISTINCT trade_date, true FROM stock_daily
            ON CONFLICT (trade_date) DO NOTHING
        """))
        session.commit()

        # Update prev/next links
        session.execute(text("""
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
        session.commit()

    logger.info("Trade calendar generated")

    # Step 5: Verify
    with Session() as session:
        stock_count = session.execute(text("SELECT COUNT(*) FROM stock_basic")).scalar()
        daily_count = session.execute(text("SELECT COUNT(*) FROM stock_daily")).scalar()
        cal_count = session.execute(text("SELECT COUNT(*) FROM trade_calendar")).scalar()
        logger.info(f"\nVerification: {stock_count} stocks, {daily_count} daily bars, {cal_count} trade days")


if __name__ == "__main__":
    asyncio.run(main())
