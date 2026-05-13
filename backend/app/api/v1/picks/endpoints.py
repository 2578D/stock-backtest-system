"""Stock picker endpoints — screen stocks by strategy or indicator criteria."""

import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.deps import get_current_user
from app.core.database import get_db
from app.engine.strategy import IStrategy, Order, Portfolio, StrategyContext
from app.engine.visual_strategy import VisualStrategy, parse_visual_rules, VisualStrategyConfig
from app.engine.market_replayer import MarketReplayer

logger = logging.getLogger(__name__)
router = APIRouter()


class PickerRequest(BaseModel):
    strategy_id: str
    market: str = "all"  # "all" | "SH" | "SZ" | "BJ" | "main"
    exclude_st: bool = True
    exclude_suspend: bool = True
    max_results: int = 50


class PickerResult(BaseModel):
    code: str
    name: str
    exchange: str
    industry: str | None
    close: float
    change_pct: float | None
    signal_reason: str


@router.post("/run")
async def run_stock_picker(
    req: PickerRequest,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    """Screen stocks by running a strategy against the latest market data.

    Loads the strategy, fetches the latest daily bar for each eligible stock,
    runs the strategy's on_bar on each, and returns stocks with buy signals.
    """
    # 1. Load strategy
    strat_row = await db.execute(
        text(
            """SELECT id, name, type, rules_json, code_content
            FROM strategy WHERE id = CAST(:id AS UUID)"""
        ),
        {"id": req.strategy_id},
    )
    strat = strat_row.fetchone()
    if not strat:
        raise HTTPException(404, "Strategy not found")

    # 2. Build strategy instance
    strategy: IStrategy
    if strat[2] == "code" and strat[4]:
        strategy = _build_code_strategy(strat[4])
    else:
        rules = strat[3] if strat[3] else {}
        config = parse_visual_rules(rules)
        strategy = VisualStrategy(config)

    # 3. Get latest trading date
    latest = await db.execute(text("SELECT MAX(trade_date) FROM stock_daily"))
    latest_date: date = latest.scalar()
    if not latest_date:
        raise HTTPException(503, "No market data available")

    # 4. Build stock pool based on filters
    conditions = ["s.status = 1"]  # active only
    params: dict = {"latest": latest_date}

    if req.market == "SH":
        conditions.append("s.exchange = 'SH'")
    elif req.market == "SZ":
        conditions.append("s.exchange = 'SZ'")
    elif req.market == "BJ":
        conditions.append("s.exchange = 'BJ'")
    elif req.market == "main":
        conditions.append("s.exchange IN ('SH', 'SZ')")
        conditions.append("s.code LIKE '60%' OR s.code LIKE '00%'")

    if req.exclude_st:
        conditions.append("s.is_st = FALSE")
    if req.exclude_suspend:
        conditions.append("s.status = 1")

    where = " AND ".join(conditions)

    # 5. Fetch eligible stocks with latest bar
    sql = text(f"""
        SELECT s.code, s.name, s.exchange, s.industry, s.is_st,
               d.open, d.high, d.low, d.close, d.volume, d.amount, d.turnover_rate,
               d2.close AS prev_close
        FROM stock_basic s
        JOIN stock_daily d ON s.code = d.code AND d.trade_date = :latest
        LEFT JOIN stock_daily d2 ON s.code = d2.code
            AND d2.trade_date = (
                SELECT MAX(trade_date) FROM stock_daily
                WHERE code = s.code AND trade_date < :latest
            )
        WHERE {where}
        ORDER BY s.code
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        return {"code": 0, "data": {"date": str(latest_date), "strategy": strat[1], "results": [], "total": 0}}

    # 6. Run strategy on each stock's latest bar
    picked: list[dict] = []
    strategy.on_init(StrategyContext(None, latest_date))

    for row in rows:
        code, name, exchange, industry, is_st = row[0], row[1], row[2], row[3], row[4]
        close = float(row[9]) if row[9] else 0
        prev_close = float(row[17]) if len(row) > 17 and row[17] else close
        change_pct = (close - prev_close) / prev_close * 100 if prev_close and prev_close > 0 else None

        if close <= 0:
            continue

        bar = {
            "code": code,
            "open": float(row[5]) if row[5] else 0,
            "high": float(row[6]) if row[6] else 0,
            "low": float(row[7]) if row[7] else 0,
            "close": close,
            "volume": float(row[10]) if row[10] else 0,
            "amount": float(row[11]) if row[11] else 0,
            "turnover_rate": float(row[12]) if len(row) > 12 and row[12] else 0,
        }

        # Prime the strategy with a small history (fake context)
        dummy_portfolio = Portfolio()
        dummy_portfolio.cash = 1_000_000.0

        try:
            # For visual strategies, prime with at least one bar to compute change_pct
            if isinstance(strategy, VisualStrategy):
                # Prime with previous bar to establish history
                strategy._bars[code] = [bar]
                strategy._latest_bar[code] = bar

            orders = strategy.on_bar(
                StrategyContext(None, latest_date),
                bar,
                dummy_portfolio,
            )

            # Look for buy orders
            buy_orders = [o for o in orders if o.side == "buy"]
            if buy_orders:
                reasons = [o.reason for o in buy_orders if o.reason]
                picked.append({
                    "code": code,
                    "name": name,
                    "exchange": exchange,
                    "industry": industry,
                    "close": close,
                    "change_pct": round(change_pct, 2) if change_pct else None,
                    "signal_reason": "; ".join(reasons) if reasons else "买入信号",
                })

                if len(picked) >= req.max_results:
                    break

        except Exception as e:
            logger.debug(f"Skipping {code}: {e}")
            continue

    strategy.on_stop(StrategyContext(None, latest_date), Portfolio())

    return {
        "code": 0,
        "data": {
            "date": str(latest_date),
            "strategy": strat[1],
            "total": len(picked),
            "results": picked,
        },
    }


def _build_code_strategy(code: str) -> IStrategy:
    """Build strategy instance from Python code string."""
    namespace = {}
    exec(code, {"IStrategy": IStrategy, "Order": Order, "__builtins__": __builtins__}, namespace)
    for name, obj in namespace.items():
        if isinstance(obj, type) and issubclass(obj, IStrategy) and obj is not IStrategy:
            return obj()
    raise ValueError("No IStrategy subclass found in strategy code")
