"""Data sync orchestrator — full init + incremental sync.

Flow:
1. Initialize: stock_basic → trade_calendar → stock_daily → adj_factor → ...
2. Incremental: daily after 15:30, sync yesterday's data
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockBasic
from app.services.data_provider import get_provider
from app.services.data_sync import normalize_code, clean_daily_bars, validate_daily_bars
from app.services.efinance_provider import EfinanceProvider

logger = logging.getLogger(__name__)


async def sync_stock_basic(
    db: AsyncSession,
    provider: Optional[EfinanceProvider] = None,
) -> int:
    """Sync A-share stock basic info from efinance.

    Returns: number of stocks inserted/updated.
    """
    if provider is None:
        provider = get_provider("efinance")

    logger.info("Syncing stock basic info...")
    df = provider.get_instruments()
    if df.empty:
        logger.warning("No stocks returned from provider")
        return 0

    count = 0
    for _, row in df.iterrows():
        try:
            vals = {
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "exchange": row.get("exchange", ""),
                "status": int(row.get("status", 1)),
            }
            if "list_date" in row and pd.notna(row["list_date"]):
                vals["list_date"] = pd.Timestamp(row["list_date"]).date()
            if "sector" in row:
                vals["sector"] = str(row["sector"])

            stmt = pg_insert(StockBasic).values(**vals)
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={k: stmt.excluded[k] for k in vals if k != "code"},
            )
            await db.execute(stmt)
            count += 1
        except Exception as e:
            logger.error(f"Failed to upsert {row.get('code', '?')}: {e}")

    await db.commit()
    logger.info(f"Stock basic sync done: {count} stocks")
    return count


async def sync_daily_bars(
    db: AsyncSession,
    codes: list[str],
    provider: Optional[EfinanceProvider] = None,
    on_progress=None,
) -> int:
    """Sync daily bars for given stock codes.

    Returns: total rows inserted.
    """
    if provider is None:
        provider = get_provider("efinance")

    total_rows = 0
    total = len(codes)

    for i, code in enumerate(codes):
        try:
            df = provider.get_daily_bars(code)
            if df.empty:
                continue

            for _, row in df.iterrows():
                await upsert_daily_row(db, row.to_dict())
            total_rows += len(df)

        except Exception as e:
            logger.error(f"Failed to sync daily bars for {code}: {e}")

        if on_progress:
            on_progress(i + 1, total)

    await db.commit()
    logger.info(f"Daily bars sync done: {total_rows} rows for {len(codes)} stocks")
    return total_rows


async def upsert_daily_row(db: AsyncSession, row: dict):
    """Insert or update a single daily bar row."""
    try:
        vals = {
            "code": row.get("code", ""),
            "trade_date": _to_date(row.get("trade_date")),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": float(row.get("volume", 0)),
            "amount": float(row.get("amount", 0)),
        }
        if "turnover_rate" in row:
            vals["turnover_rate"] = float(row.get("turnover_rate", 0))

        # Use raw SQL for performance (upsert via ON CONFLICT)
        stmt = text("""
            INSERT INTO stock_daily (code, trade_date, open, high, low, close, volume, amount, turnover_rate)
            VALUES (:code, :trade_date, :open, :high, :low, :close, :volume, :amount, :turnover_rate)
            ON CONFLICT (code, trade_date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                amount = EXCLUDED.amount,
                turnover_rate = EXCLUDED.turnover_rate
        """)
        await db.execute(stmt, vals)
    except Exception as e:
        logger.warning(f"Failed to upsert daily row for {row.get('code')} {row.get('trade_date')}: {e}")


def _to_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return pd.Timestamp(val).date()
    except Exception:
        return None


async def generate_trade_calendar(db: AsyncSession):
    """Generate trade_calendar from distinct trade_date values in stock_daily."""
    logger.info("Generating trade calendar...")
    result = await db.execute(text("""
        INSERT INTO trade_calendar (trade_date, is_trade_day)
        SELECT DISTINCT trade_date, true
        FROM stock_daily
        ON CONFLICT (trade_date) DO NOTHING
    """))
    await db.commit()

    # Update prev/next links
    await db.execute(text("""
        UPDATE trade_calendar tc
        SET
            pre_trade_date = (
                SELECT trade_date FROM trade_calendar
                WHERE trade_date < tc.trade_date
                ORDER BY trade_date DESC LIMIT 1
            ),
            next_trade_date = (
                SELECT trade_date FROM trade_calendar
                WHERE trade_date > tc.trade_date
                ORDER BY trade_date ASC LIMIT 1
            )
    """))
    await db.commit()
    logger.info("Trade calendar generated")


async def get_stock_codes(db: AsyncSession) -> list[str]:
    """Get all active stock codes from local database."""
    result = await db.execute(
        select(StockBasic.code).where(StockBasic.status == 1)
    )
    return [row[0] for row in result.fetchall()]
