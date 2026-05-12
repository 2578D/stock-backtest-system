"""Future leak prevention for backtesting.

Enforces:
- Bar timestamp never exceeds current backtest date
- Delisted stocks excluded after delist_date
- Suspend days filtered out
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)


class LookAheadGuard:
    """Validates that strategy code cannot access future data."""

    def __init__(self, stock_info: dict[str, dict] | None = None):
        """
        Args:
            stock_info: {code: {list_date, delist_date, is_st}, ...}
        """
        self._stock_info = stock_info or {}

    def is_trading(self, symbol: str, bar_date: date) -> bool:
        """Check if a stock was trading on a given date."""
        info = self._stock_info.get(symbol, {})
        list_date = info.get("list_date")
        delist_date = info.get("delist_date")

        if list_date and bar_date < list_date:
            return False
        if delist_date and bar_date > delist_date:
            return False
        return True

    def is_suspended(self, bar: dict) -> bool:
        """Detect if a bar represents a suspended trading day.

        A suspended day typically has:
        - open == close == high == low
        - volume == 0 or very close to 0
        """
        o = bar.get("open", 0)
        c = bar.get("close", 0)
        h = bar.get("high", 0)
        l_ = bar.get("low", 0)
        v = bar.get("volume", 0)

        if v == 0 and o == c == h == l_:
            return True
        return False

    def validate_bar(self, symbol: str, bar: dict, current_date: date) -> bool:
        """Return True if the bar is valid for use at current_date."""
        bar_date = bar.get("trade_date")
        if bar_date and bar_date > current_date:
            logger.warning(
                f"LookAhead: {symbol} bar date {bar_date} > current {current_date}"
            )
            return False

        if not self.is_trading(symbol, current_date):
            return False

        if self.is_suspended(bar):
            return False

        return True
