"""Strategy interface and context."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


class StrategyContext:
    """Context passed to strategy callbacks — gives access to market data window."""

    def __init__(self, data_provider: "MarketReplayer", current_date: date):
        self._provider = data_provider
        self.current_date = current_date

    def data(self, symbol: str, lookback: int = 20) -> pd.DataFrame:
        """Get last `lookback` bars for symbol up to current_date (inclusive)."""
        return self._provider.get_window(symbol, self.current_date, lookback)


class Order:
    """A strategy-generated order."""

    def __init__(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        quantity: int,
        price: Optional[float] = None,  # None = market order
        reason: str = "",
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price  # None for market orders
        self.reason = reason
        self.timestamp: date | None = None


class Portfolio:
    """Portfolio state snapshot."""

    def __init__(self):
        self.cash: float = 0.0
        self.positions: dict[str, "Position"] = {}  # symbol → Position

    @property
    def total_value(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    def clone(self) -> "Portfolio":
        p = Portfolio()
        p.cash = self.cash
        p.positions = {k: v.clone() for k, v in self.positions.items()}
        return p


class Position:
    """Single stock position."""

    def __init__(self, symbol: str, quantity: int = 0, avg_cost: float = 0.0):
        self.symbol = symbol
        self.quantity = quantity
        self.avg_cost = avg_cost
        self.current_price: float = 0.0
        self.buy_date: date | None = None

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    def clone(self) -> "Position":
        p = Position(self.symbol, self.quantity, self.avg_cost)
        p.current_price = self.current_price
        p.buy_date = self.buy_date
        return p


class IStrategy:
    """Strategy interface.

    Implement on_init / on_bar / on_stop.
    """

    def on_init(self, context: StrategyContext) -> None:
        """Called once before the backtest loop."""
        pass

    def on_bar(
        self,
        context: StrategyContext,
        bar: dict[str, float | int],
        portfolio: Portfolio,
    ) -> list[Order]:
        """Called on each bar. Return list of Orders or empty list."""
        return []

    def on_stop(self, context: StrategyContext, portfolio: Portfolio) -> None:
        """Called after the backtest loop finishes."""
        pass
