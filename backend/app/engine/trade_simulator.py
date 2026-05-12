"""Trade simulator — order matching, account management, cost calculation.

Matching rules:
- Market orders fill at bar's open price (simplified: fills at close as proxy for daily bars)
- No partial fills (simplified for daily-bar backtesting)
- Updates portfolio cash, positions, and generates fill events
"""

import logging
from datetime import date
from typing import Optional

from app.engine.events import Event, EventBus, EventType
from app.engine.risk_manager import RiskManager
from app.engine.strategy import Order, Portfolio, Position

logger = logging.getLogger(__name__)


class TradeSimulator:
    """Handles order execution, account management, and cost deduction."""

    def __init__(
        self,
        initial_capital: float,
        risk_manager: RiskManager,
        event_bus: EventBus,
    ):
        self._initial_capital = initial_capital
        self._risk = risk_manager
        self._event_bus = event_bus
        self._portfolio = Portfolio()
        self._portfolio.cash = initial_capital
        self._portfolio._current_date: date | None = None
        self._trades: list[dict] = []  # Trade history

    @property
    def portfolio(self) -> Portfolio:
        return self._portfolio

    @property
    def trades(self) -> list[dict]:
        return self._trades

    def set_date(self, current_date: date) -> None:
        """Update current backtest date (for T+1 tracking)."""
        self._portfolio._current_date = current_date

    def mark_to_market(self, bars: dict[str, dict]) -> None:
        """Update all position market prices from current bars."""
        for symbol, pos in self._portfolio.positions.items():
            if symbol in bars:
                pos.current_price = bars[symbol]["close"]

    def process_order(
        self, order: Order, bar: dict, prev_close: float | None = None
    ) -> bool:
        """Attempt to fill an order.

        Returns: True if filled, False if rejected.
        """
        symbol = order.symbol
        fill_price = order.price if order.price else bar.get("close", 0)

        # Validate
        approved, reason = self._risk.validate_order(
            order, self._portfolio, bar, prev_close
        )
        if not approved:
            self._event_bus.publish(
                Event(
                    EventType.RISK_REJECT,
                    self._portfolio._current_date or date.today(),
                    {"symbol": symbol, "order": order, "reason": reason},
                )
            )
            return False

        # Execute
        cost = self._risk.get_cost(order, fill_price)

        if order.side == "buy":
            total_cost = fill_price * order.quantity + cost
            self._portfolio.cash -= total_cost
            if symbol not in self._portfolio.positions:
                self._portfolio.positions[symbol] = Position(symbol)
            pos = self._portfolio.positions[symbol]
            new_total_cost = pos.cost_basis + fill_price * order.quantity
            pos.quantity += order.quantity
            pos.avg_cost = new_total_cost / pos.quantity if pos.quantity > 0 else 0
            pos.buy_date = self._portfolio._current_date
        else:
            revenue = fill_price * order.quantity - cost
            self._portfolio.cash += revenue
            pos = self._portfolio.positions.get(symbol)
            if pos:
                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    del self._portfolio.positions[symbol]

        # Record trade
        current = self._portfolio._current_date or date.today()
        self._trades.append({
            "symbol": symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": fill_price,
            "cost": round(cost, 4),
            "date": current,
            "reason": order.reason,
        })

        # Publish fill event
        self._event_bus.publish(
            Event(
                EventType.FILL,
                current,
                {"symbol": symbol, "side": order.side, "quantity": order.quantity, "price": fill_price},
            )
        )

        return True
