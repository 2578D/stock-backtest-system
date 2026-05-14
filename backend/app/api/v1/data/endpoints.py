"""Data endpoints — stock list, daily bars, data source management, sync control."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.deps import get_current_user
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.stock import StockBasic

router = APIRouter()


# ── Schemas ─────────────────────────────────────

class SyncRequest(BaseModel):
    cookie: str = ""


class SyncStatus(BaseModel):
    status: str = "idle"
    progress: str = ""


# ── Stock endpoints ─────────────────────────────

@router.get("/stocks")
async def list_stocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="Search by code or name"),
    exchange: str = Query("", description="Filter by exchange SH/SZ/BJ"),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """List A-share stocks with pagination and search."""
    base = select(
        StockBasic.code,
        StockBasic.name,
        StockBasic.exchange,
        StockBasic.sector,
        StockBasic.industry,
        StockBasic.list_date,
        StockBasic.status,
        StockBasic.is_st,
    )

    if keyword:
        base = base.where(
            (StockBasic.code.ilike(f"%{keyword}%"))
            | (StockBasic.name.ilike(f"%{keyword}%"))
        )
    if exchange:
        base = base.where(StockBasic.exchange == exchange.upper())

    # Count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch page
    stmt = base.offset((page - 1) * page_size).limit(page_size).order_by(StockBasic.code)
    result = await db.execute(stmt)
    rows = result.fetchall()

    data = [
        {
            "code": r.code,
            "name": r.name,
            "exchange": r.exchange,
            "sector": r.sector,
            "industry": r.industry,
            "list_date": str(r.list_date) if r.list_date else None,
            "status": r.status,
            "is_st": r.is_st,
        }
        for r in rows
    ]

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


@router.get("/stocks/{code}")
async def get_stock(code: str, db: AsyncSession = Depends(get_db)):
    """Get stock details by code."""
    result = await db.execute(
        select(StockBasic).where(StockBasic.code == code)
    )
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    return {
        "code": 0,
        "data": {
            "code": stock.code,
            "name": stock.name,
            "exchange": stock.exchange,
            "sector": stock.sector,
            "industry": stock.industry,
            "list_date": str(stock.list_date) if stock.list_date else None,
            "delist_date": str(stock.delist_date) if stock.delist_date else None,
            "status": stock.status,
            "is_st": stock.is_st,
        },
    }


# ── Daily data endpoints ────────────────────────

@router.get("/daily/{code}")
async def get_daily_bars(
    code: str,
    start_date: str = Query("", description="YYYY-MM-DD"),
    end_date: str = Query("", description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get daily OHLCV bars for a stock."""
    base = text("""
        SELECT code, trade_date, open, high, low, close, volume, amount, turnover_rate
        FROM stock_daily
        WHERE code = :code
    """)
    params = {"code": code}

    if start_date:
        base = text(str(base) + " AND trade_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        base = text(str(base) + " AND trade_date <= :end_date")
        params["end_date"] = end_date

    # Count
    count_sql = text(f"SELECT COUNT(*) FROM ({base.text}) AS sub")
    count_params = {k: v for k, v in params.items()}
    total = (await db.execute(count_sql, count_params)).scalar() or 0

    # Paginate
    base = text(f"{base.text} ORDER BY trade_date DESC LIMIT :limit OFFSET :offset")
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size

    result = await db.execute(base, params)
    rows = result.fetchall()

    data = [
        {
            "code": r.code,
            "trade_date": str(r.trade_date),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": float(r.volume),
            "amount": float(r.amount),
            "turnover_rate": float(r.turnover_rate) if r.turnover_rate else None,
        }
        for r in rows
    ]

    return {
        "code": 0,
        "data": data,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    }


# ── Data source management ──────────────────────

@router.get("/sources")
async def list_data_sources():
    """List configured data sources."""
    return {"code": 0, "data": [{"name": "efinance", "type": "api", "enabled": True}]}


# ── Sync control ────────────────────────────────

@router.post("/sync/full")
async def trigger_full_sync(
    req: SyncRequest,
    _current_user=Depends(get_current_user),
):
    """Trigger full initial data sync (async via Celery)."""
    from app.celery_app import celery_app
    from app.tasks import full_init_sync

    task = celery_app.send_task(
        "data_sync.full_init_sync",
        kwargs={"cookie": req.cookie},
    )
    return {
        "code": 0,
        "message": "Full sync started",
        "data": {"task_id": task.id},
    }


@router.post("/sync/incremental")
async def trigger_incremental_sync(
    _current_user=Depends(get_current_user),
):
    """Trigger incremental sync for recent trading days."""
    from app.celery_app import celery_app
    task = celery_app.send_task(
        "data_sync.incremental_sync",
        kwargs={"lookback_days": 5},
    )
    return {
        "code": 0,
        "message": "Incremental sync started",
        "data": {"task_id": task.id},
    }


@router.get("/sync/status")
async def get_sync_status(
    _current_user=Depends(get_current_user),
):
    """Get current sync progress."""
    redis = await get_redis()
    keys = await redis.keys("sync:progress:*")
    if not keys:
        return {"code": 0, "data": {"status": "idle", "progress": ""}}

    # Get the most recent progress
    for key in sorted(keys, reverse=True):
        progress = await redis.get(key)
        if progress:
            return {"code": 0, "data": {"status": "running", "progress": progress}}

    return {"code": 0, "data": {"status": "idle", "progress": ""}}


@router.get("/sync/stats")
async def get_data_stats(db: AsyncSession = Depends(get_db)):
    """Get data overview statistics for dashboard."""
    stock_count = (await db.execute(
        select(func.count()).select_from(StockBasic)
    )).scalar() or 0

    active_count = (await db.execute(
        select(func.count()).where(StockBasic.status == 1)
    )).scalar() or 0

    # Latest data date
    latest = await db.execute(text(
        "SELECT MAX(trade_date) FROM stock_daily"
    ))
    latest_date = latest.scalar()

    return {
        "code": 0,
        "data": {
            "total_stocks": stock_count,
            "active_stocks": active_count,
            "latest_data_date": str(latest_date) if latest_date else None,
        },
    }
