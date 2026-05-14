"""Backtest endpoints — CRUD, execution, results."""

import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.deps import get_current_user
from app.core.database import get_db
from app.tasks.backtest_task import run_backtest

router = APIRouter()


class CreateBacktestRequest(BaseModel):
    strategy_id: str
    name: str | None = None
    start_date: date
    end_date: date
    stock_pool: dict = {}
    initial_capital: float = 1_000_000.0
    position_mode: str = "fixed"
    benchmark: str = "000300.SH"
    adjust_mode: str = "forward"
    cost_config: dict = {}


@router.post("")
async def create_backtest(
    req: CreateBacktestRequest,
    db: AsyncSession = Depends(get_db),
    # user = Depends(get_current_user),  # TODO: enable after auth is wired
):
    """Create and start a new backtest task."""
    task_id = str(uuid.uuid4())

    await db.execute(
        text(
            """INSERT INTO backtest_task
            (id, user_id, strategy_id, name, start_date, end_date, stock_pool,
             initial_capital, position_mode, benchmark, adjust_mode, cost_config, status)
            VALUES (CAST(:id AS UUID), CAST(:uid AS UUID), CAST(:sid AS UUID), :name,
             :start, :end, CAST(:pool AS JSONB), :cap, :mode, :bench, :adj,
             CAST(:cost AS JSONB), 'pending')"""
        ),
        {
            "id": task_id,
            "uid": "00000000-0000-0000-0000-000000000000",  # placeholder
            "sid": req.strategy_id,
            "name": req.name or f"回测 {req.start_date}~{req.end_date}",
            "start": req.start_date,
            "end": req.end_date,
            "pool": json.dumps(req.stock_pool),
            "cap": req.initial_capital,
            "mode": req.position_mode,
            "bench": req.benchmark,
            "adj": req.adjust_mode,
            "cost": json.dumps(req.cost_config),
        },
    )
    await db.commit()

    # Start Celery task
    run_backtest.delay(task_id)

    return {
        "code": 0,
        "data": {"task_id": task_id, "status": "pending"},
    }


@router.get("")
async def list_backtests(db: AsyncSession = Depends(get_db)):
    """List all backtest tasks."""
    result = await db.execute(
        text(
            """SELECT id, name, strategy_id, start_date, end_date, status, progress,
            initial_capital, created_at FROM backtest_task ORDER BY created_at DESC LIMIT 50"""
        )
    )
    rows = result.fetchall()
    return {
        "code": 0,
        "data": [
            {
                "id": str(r[0]), "name": r[1], "strategy_id": str(r[2]),
                "start_date": str(r[3]), "end_date": str(r[4]),
                "status": r[5], "progress": r[6],
                "initial_capital": float(r[7]), "created_at": str(r[8]) if r[8] else None,
            }
            for r in rows
        ],
    }


@router.get("/{task_id}")
async def get_backtest(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get backtest task details."""
    result = await db.execute(
        text(
            """SELECT id, name, strategy_id, start_date, end_date, status, progress,
            initial_capital, stock_pool, benchmark, adjust_mode, error_message,
            started_at, completed_at, created_at
            FROM backtest_task WHERE id = CAST(:id AS UUID)"""
        ),
        {"id": task_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Task not found")

    return {
        "code": 0,
        "data": {
            "id": str(row[0]), "name": row[1], "strategy_id": str(row[2]),
            "start_date": str(row[3]), "end_date": str(row[4]),
            "status": row[5], "progress": row[6],
            "initial_capital": float(row[7]),
            "stock_pool": row[8], "benchmark": row[9], "adjust_mode": row[10],
            "error_message": row[11],
            "started_at": str(row[12]) if row[12] else None,
            "completed_at": str(row[13]) if row[13] else None,
            "created_at": str(row[14]) if row[14] else None,
        },
    }


@router.get("/{task_id}/result")
async def get_backtest_result(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get backtest performance metrics."""
    result = await db.execute(
        text(
            """SELECT total_return, annual_return, max_drawdown, sharpe_ratio,
            calmar_ratio, sortino_ratio, win_rate, profit_loss_ratio, trade_count,
            annual_volatility, benchmark_return, excess_return, max_drawdown_days,
            avg_hold_days, max_single_profit, max_single_loss,
            equity_curve, benchmark_curve, daily_returns
            FROM backtest_result WHERE task_id = CAST(:id AS UUID)"""
        ),
        {"id": task_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Result not found")

    return {
        "code": 0,
        "data": {
            "total_return": float(row[0]),
            "annual_return": float(row[1]),
            "max_drawdown": float(row[2]),
            "sharpe_ratio": float(row[3]),
            "calmar_ratio": float(row[4]) if row[4] else None,
            "sortino_ratio": float(row[5]) if row[5] else None,
            "win_rate": float(row[6]),
            "profit_loss_ratio": float(row[7]),
            "trade_count": row[8],
            "annual_volatility": float(row[9]),
            "benchmark_return": float(row[10]) if row[10] else None,
            "excess_return": float(row[11]) if row[11] else None,
            "max_drawdown_days": row[12],
            "avg_hold_days": float(row[13]) if row[13] else None,
            "max_single_profit": float(row[14]) if row[14] else None,
            "max_single_loss": float(row[15]) if row[15] else None,
            "equity_curve": row[16] if isinstance(row[16], dict) else (json.loads(row[16]) if row[16] else {}),
            "benchmark_curve": row[17] if isinstance(row[17], dict) else (json.loads(row[17]) if row[17] else {}),
            "daily_returns": row[18] if isinstance(row[18], list) else (json.loads(row[18]) if row[18] else []),
        },
    }


@router.get("/{task_id}/trades")
async def get_backtest_trades(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get backtest trade records."""
    result = await db.execute(
        text(
            """SELECT stock_code, buy_date, buy_price, buy_reason,
            sell_date, sell_price, sell_reason, quantity, hold_days,
            return_rate, return_amount
            FROM backtest_trade WHERE task_id = CAST(:id AS UUID)
            ORDER BY buy_date"""
        ),
        {"id": task_id},
    )
    rows = result.fetchall()
    return {
        "code": 0,
        "data": [
            {
                "stock_code": r[0],
                "buy_date": str(r[1]) if r[1] else None,
                "buy_price": float(r[2]) if r[2] else None,
                "buy_reason": r[3],
                "sell_date": str(r[4]) if r[4] else None,
                "sell_price": float(r[5]) if r[5] else None,
                "sell_reason": r[6],
                "quantity": r[7],
                "hold_days": r[8],
                "return_rate": float(r[9]) if r[9] else None,
                "return_amount": float(r[10]) if r[10] else None,
            }
            for r in rows
        ],
    }


@router.post("/{task_id}/stop")
async def stop_backtest(task_id: str, db: AsyncSession = Depends(get_db)):
    """Stop a running backtest."""
    await db.execute(
        text(
            """UPDATE backtest_task SET status = 'failed',
            error_message = 'User stopped', completed_at = NOW()
            WHERE id = CAST(:id AS UUID) AND status = 'running'"""
        ),
        {"id": task_id},
    )
    await db.commit()
    return {"code": 0, "message": "stopped"}
