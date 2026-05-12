"""Result collector — tracks equity curve, daily portfolio snapshots, and handles progress."""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Optional

from app.engine.events import Event, EventType

logger = logging.getLogger(__name__)


class ResultCollector:
    """Collects backtest results incrementally during the run.

    Tracks:
    - Daily NAV / equity curve
    - Daily returns
    - Position snapshots
    - Signal log (firehose of everything)
    """

    def __init__(self):
        self.equity_curve: dict[str, float] = {}       # date_iso → nav
        self.daily_returns: dict[str, float] = {}      # date_iso → return
        self.position_snapshots: dict[str, dict] = {}  # date_iso → {symbol: {qty, price, value}}
        self._on_progress: Optional[Callable[[int, int], None]] = None   # (current_day, total_days)
        self._total_days: int = 0
        self._current_day: int = 0

    def set_progress_callback(self, fn: Callable[[int, int], None], total_days: int) -> None:
        self._on_progress = fn
        self._total_days = total_days

    def record_day(self, dt: date, portfolio_value: float, daily_return: float,
                   positions: dict[str, dict]) -> None:
        """Record a day's results."""
        key = dt.isoformat()
        self.equity_curve[key] = portfolio_value
        self.daily_returns[key] = daily_return
        self.position_snapshots[key] = positions

        self._current_day += 1
        if self._on_progress and self._total_days > 0:
            pct = int(self._current_day / self._total_days * 100)
            self._on_progress(self._current_day, self._total_days)

    def get_equity_curve(self) -> dict[str, float]:
        return self.equity_curve

    def get_daily_returns(self) -> list[float]:
        return list(self.daily_returns.values())

    def get_daily_returns_with_dates(self) -> dict[str, float]:
        return self.daily_returns
