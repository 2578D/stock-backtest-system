"""Dashboard overview stats."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.deps import get_current_user
from app.core.database import get_db
from app.models.stock import StockBasic

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Get dashboard overview statistics."""
    # Stock counts
    stock_count = (
        await db.execute(select(func.count()).select_from(StockBasic))
    ).scalar() or 0
    active_count = (
        await db.execute(
            select(func.count()).where(StockBasic.status == 1)
        )
    ).scalar() or 0

    # Strategy count
    strategy_count = (
        await db.execute(text("SELECT COUNT(*) FROM strategy"))
    ).scalar() or 0

    # Backtest counts
    backtest_total = (
        await db.execute(text("SELECT COUNT(*) FROM backtest_task"))
    ).scalar() or 0
    backtest_completed = (
        await db.execute(
            text("SELECT COUNT(*) FROM backtest_task WHERE status = 'completed'")
        )
    ).scalar() or 0
    backtest_running = (
        await db.execute(
            text("SELECT COUNT(*) FROM backtest_task WHERE status = 'running'")
        )
    ).scalar() or 0

    # Daily data stats
    daily_dates = (
        await db.execute(text("SELECT COUNT(DISTINCT trade_date) FROM stock_daily"))
    ).scalar() or 0
    daily_rows = (
        await db.execute(text("SELECT COUNT(*) FROM stock_daily"))
    ).scalar() or 0
    latest_date = (
        await db.execute(text("SELECT MAX(trade_date) FROM stock_daily"))
    ).scalar()

    # Recent backtests (top 5)
    recent = await db.execute(
        text(
            """SELECT id, name, strategy_id, status, progress, created_at
            FROM backtest_task ORDER BY created_at DESC LIMIT 5"""
        )
    )
    recent_backtests = [
        {
            "id": str(r[0]),
            "name": r[1],
            "strategy_id": str(r[2]),
            "status": r[3],
            "progress": r[4],
            "created_at": str(r[5]) if r[5] else None,
        }
        for r in recent.fetchall()
    ]

    # Top strategies by backtest count
    top_strategies = await db.execute(
        text(
            """SELECT s.id, s.name, s.type, COUNT(bt.id) as run_count
            FROM strategy s LEFT JOIN backtest_task bt ON s.id = bt.strategy_id
            GROUP BY s.id, s.name, s.type
            ORDER BY run_count DESC LIMIT 5"""
        )
    )
    top_strategy_list = [
        {
            "id": str(r[0]),
            "name": r[1],
            "type": r[2],
            "run_count": r[3],
        }
        for r in top_strategies.fetchall()
    ]

    return {
        "code": 0,
        "data": {
            "stocks": {
                "total": stock_count,
                "active": active_count,
            },
            "strategies": {
                "total": strategy_count,
                "top": top_strategy_list,
            },
            "backtests": {
                "total": backtest_total,
                "completed": backtest_completed,
                "running": backtest_running,
                "recent": recent_backtests,
            },
            "data": {
                "latest_date": str(latest_date) if latest_date else None,
                "distinct_dates": daily_dates,
                "total_rows": daily_rows,
            },
        },
    }
