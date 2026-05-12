"""Performance metrics calculator.

Input: list of daily returns (float), benchmark returns (optional).
All metrics assume 252 trading days per year.
"""

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PerformanceMetrics:
    """Standard backtest performance metrics."""

    total_return: float = 0.0
    total_return_amount: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float | None = None
    excess_return: float | None = None
    max_drawdown: float = 0.0
    max_drawdown_days: int | None = None
    annual_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float | None = None
    sortino_ratio: float | None = None
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    trade_count: int = 0
    avg_hold_days: float | None = None
    max_single_profit: float | None = None
    max_single_loss: float | None = None


def compute_metrics(
    daily_returns: list[float],
    initial_capital: float = 1_000_000,
    benchmark_returns: list[float] | None = None,
    trades: list[dict] | None = None,
    risk_free_rate: float = 0.02,
) -> PerformanceMetrics:
    """Compute full performance metrics from daily returns and optional trade data."""
    m = PerformanceMetrics()

    if not daily_returns:
        return m

    n = len(daily_returns)
    # Cumulative equity curve
    equity = [initial_capital]
    for r in daily_returns:
        equity.append(equity[-1] * (1 + r))
    equity = equity[1:]  # Skip initial

    # Total return
    m.total_return = (equity[-1] / initial_capital - 1) if equity else 0
    m.total_return_amount = equity[-1] - initial_capital if equity else 0

    # Annualized return
    if n > 0:
        m.annual_return = (1 + m.total_return) ** (252 / n) - 1

    # Max drawdown
    peak = equity[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_days = 0
    for i, val in enumerate(equity):
        if val > peak:
            peak = val
            peak_idx = i
        dd = (peak - val) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_days = i - peak_idx
    m.max_drawdown = max_dd
    m.max_drawdown_days = max_dd_days if max_dd_days > 0 else None

    # Annual volatility
    if n > 1:
        mean_ret = sum(daily_returns) / n
        variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (n - 1)
        m.annual_volatility = math.sqrt(variance) * math.sqrt(252)

    # Sharpe ratio
    if m.annual_volatility > 0:
        m.sharpe_ratio = (m.annual_return - risk_free_rate) / m.annual_volatility

    # Calmar ratio
    if m.max_drawdown > 0:
        m.calmar_ratio = m.annual_return / m.max_drawdown

    # Sortino ratio (downside deviation)
    down_returns = [r for r in daily_returns if r < 0]
    if down_returns:
        down_mean = sum(down_returns) / len(down_returns)
        down_variance = sum((r - down_mean) ** 2 for r in down_returns) / (len(down_returns) - 1) if len(down_returns) > 1 else 0
        down_dev = math.sqrt(down_variance) * math.sqrt(252)
        if down_dev > 0:
            m.sortino_ratio = (m.annual_return - risk_free_rate) / down_dev

    # Benchmark / excess return
    if benchmark_returns:
        bench_total = 1.0
        for br in benchmark_returns:
            bench_total *= (1 + br)
        m.benchmark_return = bench_total - 1
        m.excess_return = m.total_return - m.benchmark_return

    # Trade statistics
    if trades:
        m.trade_count = len(trades)
        sell_trades = [t for t in trades if t.get("side") == "sell"]
        if sell_trades:
            # Group into round-trips for win rate
            round_trips = _group_trades(trades)
            wins = [rt for rt in round_trips if rt["pnl"] > 0]
            m.win_rate = len(wins) / len(round_trips) if round_trips else 0
            total_win = sum(rt["pnl"] for rt in wins) if wins else 0
            total_loss = abs(sum(rt["pnl"] for rt in round_trips if rt["pnl"] <= 0)) if len(wins) < len(round_trips) else 1
            m.profit_loss_ratio = total_win / total_loss if total_loss > 0 else 0

            pnls = [rt["pnl"] for rt in round_trips]
            if pnls:
                m.max_single_profit = max(pnls)
                m.max_single_loss = min(pnls)

            holds = [rt.get("hold_days", 0) for rt in round_trips if rt.get("hold_days")]
            if holds:
                m.avg_hold_days = sum(holds) / len(holds)

    return m


def _group_trades(trades: list[dict]) -> list[dict]:
    """Group trades into round-trips for per-symbol PnL calculation.

    Simple approach: match buys with subsequent sells per symbol.
    """
    from collections import defaultdict

    buys: dict[str, list[dict]] = defaultdict(list)
    round_trips: list[dict] = []

    for t in trades:
        sym = t["symbol"]
        if t["side"] == "buy":
            buys[sym].append(t)
        else:
            if buys[sym]:
                buy = buys[sym].pop(0)
                pnl = (t["price"] - buy["price"]) * t["quantity"]
                hold_days = (
                    (t["date"] - buy["date"]).days
                    if t.get("date") and buy.get("date")
                    else 0
                )
                round_trips.append({
                    "symbol": sym,
                    "pnl": pnl,
                    "hold_days": hold_days,
                    "buy_date": buy.get("date"),
                    "sell_date": t.get("date"),
                })

    return round_trips
