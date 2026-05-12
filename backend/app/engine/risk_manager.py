"""Risk manager — A-share specific risk rules.

Enforces:
- T+1 (cannot sell on same day as buy)
- Price limits (主板±10%, 创业板/科创板±20%, 北交所±30%, ST±5%)
- Single position max % of total capital
- Max number of concurrent positions
- Minimum trade unit: 100 shares (1 lot)
- Trading costs: commission, stamp tax, transfer fee
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.engine.strategy import Order, Portfolio, Position

logger = logging.getLogger(__name__)

# Exchange → price limit rate
LIMIT_RATES = {"SH": 0.10, "SZ": 0.10, "BJ": 0.30}


@dataclass
class RiskConfig:
    max_position_pct: float = 0.30       # Max single-stock position as % of total capital
    max_positions: int = 10              # Max concurrent positions
    min_shares: int = 100                # Minimum trade unit (1 lot = 100 shares)
    commission_rate: float = 0.0003      # Commission 0.03%
    commission_min: float = 5.0          # Min commission per trade
    stamp_tax_rate: float = 0.001        # Stamp tax 0.1% (sell only)
    transfer_fee_rate: float = 0.000015  # Transfer fee 0.0015%


class RiskManager:
    """Validates orders against A-share rules."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self._info: dict[str, dict] = {}  # stock info cache

    def set_stock_info(self, stock_info: dict[str, dict]) -> None:
        """Pre-load stock info for limit-price calculation.

        stock_info: {code: {exchange, is_st, sector}, ...}
        """
        self._info = stock_info

    def _get_limit_rate(self, symbol: str) -> float:
        info = self._info.get(symbol, {})
        if info.get("is_st"):
            return 0.05
        exchange = info.get("exchange", "SH")
        sector = info.get("sector", "主板")
        # 创业板/科创板 use 20%, 北交所 30%
        if symbol.startswith("300") or symbol.startswith("301"):
            return 0.20
        if symbol.startswith("688"):
            return 0.20
        if symbol.startswith("8") or symbol.startswith("92"):
            return 0.30
        return 0.10

    def calc_limit_prices(self, symbol: str, prev_close: float) -> tuple[float, float]:
        """Return (limit_up, limit_down) for a stock."""
        rate = self._get_limit_rate(symbol)
        limit_up = round(prev_close * (1 + rate), 2)
        limit_down = round(prev_close * (1 - rate), 2)
        return limit_up, limit_down

    def validate_order(
        self,
        order: Order,
        portfolio: Portfolio,
        bar: dict,
        prev_close: float | None = None,
    ) -> tuple[bool, str]:
        """Validate an order against all risk rules.

        Returns: (approved, reason)
        """
        symbol = order.symbol
        price = order.price or bar.get("close", 0)
        close = bar.get("close", price)

        # 1. Price limit check
        if prev_close and prev_close > 0:
            limit_up, limit_down = self.calc_limit_prices(symbol, prev_close)
            if order.side == "buy" and close >= limit_up:
                return False, f"涨停不可买入: {close} >= {limit_up}"
            if order.side == "sell" and close <= limit_down:
                return False, f"跌停不可卖出: {close} <= {limit_down}"

        # 2. T+1 check (only for sell)
        if order.side == "sell":
            pos = portfolio.positions.get(symbol)
            if pos and pos.buy_date == portfolio._current_date:
                return False, "T+1: 当日买入不可卖出"

        # 3. Position size check (for buy)
        if order.side == "buy":
            total_value = portfolio.total_value
            proposed_value = price * order.quantity
            if total_value > 0 and proposed_value / total_value > self.config.max_position_pct:
                return False, (
                    f"单票仓位超限: {proposed_value / total_value * 100:.1f}% "
                    f"> {self.config.max_position_pct * 100:.0f}%"
                )

        # 4. Max positions check (for buy of new stock)
        if order.side == "buy" and symbol not in portfolio.positions:
            if len(portfolio.positions) >= self.config.max_positions:
                return False, f"持仓数超限: {len(portfolio.positions)} >= {self.config.max_positions}"

        # 5. Min shares check
        if order.quantity < self.config.min_shares:
            return False, f"低于最小交易单位: {order.quantity} < {self.config.min_shares}"
        if order.quantity % self.config.min_shares != 0:
            # Round down to nearest lot
            order.quantity = (order.quantity // self.config.min_shares) * self.config.min_shares
            if order.quantity == 0:
                return False, "调整后数量为0"

        # 6. Sufficient cash (buy) / shares (sell)
        if order.side == "buy":
            required = price * order.quantity + self._calc_cost(order, price)
            if required > portfolio.cash:
                # Adjust quantity to available cash
                affordable_qty = int(
                    (portfolio.cash - self.config.commission_min)
                    / (price * (1 + self.config.commission_rate))
                )
                affordable_qty = (affordable_qty // self.config.min_shares) * self.config.min_shares
                if affordable_qty <= 0:
                    return False, f"资金不足: 需要 {required:.2f}, 可用 {portfolio.cash:.2f}"
                order.quantity = affordable_qty
        else:
            pos = portfolio.positions.get(symbol)
            if not pos or pos.quantity < order.quantity:
                actual = pos.quantity if pos else 0
                if actual <= 0:
                    return False, f"无持仓: {symbol}"
                order.quantity = actual

        return True, ""

    def _calc_cost(self, order: Order, price: float) -> float:
        """Calculate transaction cost for an order."""
        turnover = price * order.quantity
        commission = max(turnover * self.config.commission_rate, self.config.commission_min)
        stamp_tax = turnover * self.config.stamp_tax_rate if order.side == "sell" else 0
        transfer_fee = turnover * self.config.transfer_fee_rate
        return commission + stamp_tax + transfer_fee

    def get_cost(self, order: Order, price: float) -> float:
        """Public cost calculator."""
        return self._calc_cost(order, price)
