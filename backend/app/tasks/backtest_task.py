"""Celery tasks for backtest execution."""

import json
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery_app
from app.core.config import get_settings
from app.engine.backtest import BacktestConfig, BacktestEngine
from app.engine.strategy import IStrategy
from app.engine.visual_strategy import VisualStrategy, parse_visual_rules, VisualStrategyConfig

logger = logging.getLogger(__name__)

settings = get_settings()

# Sync engine for Celery workers
_sync_engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)
SyncSession = sessionmaker(bind=_sync_engine)


def _update_task_status(task_id: str, status: str, progress: int = 0, error: str = "") -> None:
    """Update backtest_task status in DB."""
    with SyncSession() as s:
        s.execute(
            text(
                """UPDATE backtest_task SET status = :status, progress = :progress,
                error_message = CASE WHEN :error != '' THEN :error ELSE error_message END
                WHERE id = :id"""
            ),
            {"status": status, "progress": progress, "error": error, "id": task_id},
        )
        if status == "running" and progress == 0:
            s.execute(
                text("UPDATE backtest_task SET started_at = NOW() WHERE id = :id"),
                {"id": task_id},
            )
        if status in ("completed", "failed"):
            s.execute(
                text("UPDATE backtest_task SET completed_at = NOW() WHERE id = :id"),
                {"id": task_id},
            )
        s.commit()


def _build_config(task: dict) -> BacktestConfig:
    """Build BacktestConfig from DB task row."""
    return BacktestConfig(
        stock_pool=task.get("stock_pool", {}).get("symbols", []) if isinstance(task.get("stock_pool"), dict) else [],
        start_date=task["start_date"],
        end_date=task["end_date"],
        initial_capital=float(task.get("initial_capital", 1_000_000)),
        benchmark=task.get("benchmark", "000300.SH"),
        position_mode=task.get("position_mode", "fixed"),
        adjust_mode=task.get("adjust_mode", "forward"),
    )


@celery_app.task(bind=True, name="run_backtest")
def run_backtest(self, task_id: str, strategy_code: str = "") -> dict:
    """Execute a backtest task asynchronously.

    Args:
        task_id: UUID of the BacktestTask in DB
        strategy_code: Python code of the strategy (exec'd into a class)
    """
    task_uuid = task_id
    logger.info(f"Starting backtest task {task_uuid}")

    try:
        _update_task_status(task_uuid, "running", progress=0)

        # Load task config from DB
        with SyncSession() as session:
            row = session.execute(
                text(
                    """SELECT id, strategy_id, start_date, end_date, stock_pool,
                    initial_capital, position_mode, benchmark, adjust_mode, cost_config
                    FROM backtest_task WHERE id = CAST(:id AS UUID)"""
                ),
                {"id": task_uuid},
            ).fetchone()

            if not row:
                raise ValueError(f"Task {task_uuid} not found")

            task_dict = dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(
                ["id", "strategy_id", "start_date", "end_date", "stock_pool",
                 "initial_capital", "position_mode", "benchmark", "adjust_mode", "cost_config"],
                row
            ))

            # Load strategy
            strat_row = session.execute(
                text("SELECT type, rules_json, code_content FROM strategy WHERE id = CAST(:id AS UUID)"),
                {"id": str(task_dict["strategy_id"])},
            ).fetchone()

        config = _build_config(task_dict)

        # Build strategy instance
        if strategy_code:
            strategy = _build_code_strategy(strategy_code)
        elif strat_row:
            if strat_row[0] == "code" and strat_row[2]:
                strategy = _build_code_strategy(strat_row[2])
            else:
                # Visual strategy — compile rules into VisualStrategy
                rules = strat_row[1] if strat_row[1] else {}
                config = parse_visual_rules(rules)
                strategy = VisualStrategy(config)
        else:
            strategy = _SimpleStrategy()

        # Run engine
        engine = BacktestEngine(config, SyncSession)
        engine.set_strategy(strategy)

        def progress_cb(current, total):
            pct = int(current / total * 100) if total > 0 else 0
            _update_task_status(task_uuid, "running", progress=pct)

        engine.collector.set_progress_callback(progress_cb, len(engine.market._all_dates))
        result = engine.run()

        # Persist results
        _save_result(task_uuid, config, result)

        _update_task_status(task_uuid, "completed", progress=100)

        return {
            "task_id": task_uuid,
            "status": "completed",
            "total_return": result.metrics.total_return,
            "sharpe": result.metrics.sharpe_ratio,
            "max_drawdown": result.metrics.max_drawdown,
        }

    except Exception as e:
        logger.exception(f"Backtest task {task_uuid} failed")
        _update_task_status(task_uuid, "failed", progress=0, error=str(e))
        raise


def _save_result(task_id: str, config: BacktestConfig, result) -> None:
    """Persist backtest result to DB."""
    m = result.metrics
    with SyncSession() as s:
        # Result
        s.execute(
            text(
                """INSERT INTO backtest_result
                (task_id, total_return, total_return_amount, annual_return,
                max_drawdown, max_drawdown_days, annual_volatility,
                sharpe_ratio, calmar_ratio, sortino_ratio,
                win_rate, profit_loss_ratio, trade_count,
                avg_hold_days, max_single_profit, max_single_loss,
                equity_curve, daily_returns)
                VALUES (:tid, :tr, :tra, :ar, :mdd, :mddd, :av, :sr, :cr, :sor,
                :wr, :plr, :tc, :ahd, :msp, :msl, :ec, :dr)
                ON CONFLICT (task_id) DO UPDATE SET
                total_return = EXCLUDED.total_return,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                max_drawdown = EXCLUDED.max_drawdown"""
            ),
            {
                "tid": task_id,
                "tr": m.total_return,
                "tra": m.total_return_amount,
                "ar": m.annual_return,
                "mdd": m.max_drawdown,
                "mddd": m.max_drawdown_days,
                "av": m.annual_volatility,
                "sr": m.sharpe_ratio,
                "cr": m.calmar_ratio,
                "sor": m.sortino_ratio,
                "wr": m.win_rate,
                "plr": m.profit_loss_ratio,
                "tc": m.trade_count,
                "ahd": m.avg_hold_days,
                "msp": m.max_single_profit,
                "msl": m.max_single_loss,
                "ec": json.dumps(result.equity_curve),
                "dr": json.dumps(list(result.daily_returns.values())),
            },
        )

        # Trades
        for t in result.trades:
            s.execute(
                text(
                    """INSERT INTO backtest_trade
                    (task_id, stock_code, buy_date, buy_price, sell_date, sell_price,
                    quantity, hold_days, return_rate, return_amount)
                    VALUES (:tid, :sc, :bd, :bp, :sd, :sp, :qty, :hd, :rr, :ra)"""
                ),
                {
                    "tid": task_id,
                    "sc": t["symbol"],
                    "bd": t["date"] if t["side"] == "buy" else None,
                    "bp": t["price"] if t["side"] == "buy" else None,
                    "sd": t["date"] if t["side"] == "sell" else None,
                    "sp": t["price"] if t["side"] == "sell" else None,
                    "qty": t["quantity"],
                    "hd": 0,
                    "rr": 0,
                    "ra": 0,
                },
            )

        s.commit()


def _build_code_strategy(code: str) -> IStrategy:
    """Build a strategy instance from Python code string via exec."""
    namespace = {}
    exec(code, {"IStrategy": IStrategy, "Order": Order, "__builtins__": __builtins__}, namespace)
    for name, obj in namespace.items():
        if isinstance(obj, type) and issubclass(obj, IStrategy) and obj is not IStrategy:
            return obj()
    raise ValueError("No IStrategy subclass found in strategy code")


class _SimpleStrategy(IStrategy):
    """Minimal pass-through strategy for testing."""
    pass
