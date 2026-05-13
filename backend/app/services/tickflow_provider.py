"""TickFlow data provider — batch klines via TickFlow Free API.

Fast, concurrent batch pull replacing efinance one-by-one sync.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TickFlowProvider:
    """Market data provider backed by TickFlow Free API."""

    def __init__(self):
        self._tf = None

    @property
    def tf(self):
        if self._tf is None:
            from tickflow import TickFlow
            self._tf = TickFlow.free()
        return self._tf

    def fetch_batch(
        self,
        codes: list[str],
        period: str = "1d",
        count: int = 10000,
    ) -> dict[str, list[dict]]:
        """Fetch klines for multiple symbols in one batch call.

        Returns: {symbol: [{trade_date, open, high, low, close, volume, amount}, ...]}
        """
        if not codes:
            return {}

        import pandas as pd

        try:
            dfs = self.tf.klines.batch(
                codes,
                period=period,
                count=count,
                as_dataframe=True,
                show_progress=False,
            )
        except Exception as e:
            logger.error(f"TickFlow batch fetch failed: {e}")
            return {}

        result = {}
        for sym in codes:
            df = dfs.get(sym)
            if df is None or df.empty:
                continue
            bars = []
            for _, row in df.iterrows():
                td = str(row.get("trade_date", ""))[:10]
                if not td:
                    continue
                bars.append({
                    "trade_date": td,
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": float(row.get("volume", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                })
            if bars:
                result[sym] = bars

        return result
