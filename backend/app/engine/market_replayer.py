"""Market data replayer — loads daily bars from DB and replays chronologically."""

import logging
from collections import defaultdict
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MarketReplayer:
    """Loads stock daily data and replays bar-by-bar in chronological order."""

    def __init__(self, db_session_factory, stock_pool: list[str], start_date: date, end_date: date, period: str = "daily"):
        self._session_factory = db_session_factory
        self._stock_pool = stock_pool
        self._start_date = start_date
        self._end_date = end_date
        self._period = period  # "daily" | "weekly" | "monthly"

        # symbol → DataFrame (index=date, columns=open/high/low/close/volume/amount)
        self._data: dict[str, pd.DataFrame] = {}
        # symbol → list of dates (chronological)
        self._dates: dict[str, list[date]] = {}
        # All trade dates in range (union of all symbols' dates)
        self._all_dates: list[date] = []
        # Current index in _all_dates
        self._cursor: int = 0

    def load(self) -> None:
        """Load all required data from PostgreSQL."""
        logger.info(
            f"Loading data for {len(self._stock_pool)} stocks "
            f"from {self._start_date} to {self._end_date}"
        )

        all_data: dict[str, pd.DataFrame] = {}

        with self._session_factory() as session:
            # Load in chunks to avoid memory issues
            chunk_size = 500
            for i in range(0, len(self._stock_pool), chunk_size):
                chunk = self._stock_pool[i : i + chunk_size]
                placeholders = ",".join([f"'{c}'" for c in chunk])
                result = session.execute(
                    text(
                        f"""SELECT code, trade_date, open, high, low, close, volume, amount
                        FROM stock_daily
                        WHERE code IN ({placeholders})
                        AND trade_date >= :start AND trade_date <= :end
                        ORDER BY code, trade_date"""
                    ),
                    {"start": self._start_date, "end": self._end_date},
                )
                rows = result.fetchall()

                for code in chunk:
                    all_data.setdefault(code, [])

                for row in rows:
                    all_data[row.code].append({
                        "trade_date": row.trade_date,
                        "open": float(row.open),
                        "high": float(row.high),
                        "low": float(row.low),
                        "close": float(row.close),
                        "volume": float(row.volume),
                        "amount": float(row.amount),
                    })

        # Build DataFrames
        all_trade_dates: set[date] = set()
        for code in self._stock_pool:
            rows_list = all_data.get(code, [])
            if not rows_list:
                continue
            df = pd.DataFrame(rows_list)
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            df = df.set_index("trade_date").sort_index()
            self._data[code] = df
            dates_list = sorted(df.index.tolist())
            self._dates[code] = dates_list
            all_trade_dates.update(dates_list)

        self._all_dates = sorted(all_trade_dates)
        # Filter to range
        self._all_dates = [
            d for d in self._all_dates if self._start_date <= d <= self._end_date
        ]
        logger.info(f"Loaded data: {len(self._all_dates)} trading days, {len(self._data)} stocks")

        # Resample if needed
        if self._period != "daily":
            self._resample()

    def _resample(self) -> None:
        """Resample daily data to weekly or monthly bars."""
        rule = "W" if self._period == "weekly" else "M"
        logger.info(f"Resampling daily data to {self._period} ({rule})...")

        new_data: dict[str, pd.DataFrame] = {}
        all_trade_dates: set[date] = set()

        for symbol, df in self._data.items():
            if df.empty:
                continue
            resampled = df.resample(rule).agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
            }).dropna()
            if resampled.empty:
                continue
            new_data[symbol] = resampled
            dates_list = sorted(resampled.index.tolist())
            self._dates[symbol] = [d.date() if hasattr(d, 'date') else d for d in dates_list]
            all_trade_dates.update(self._dates[symbol])

        self._data = new_data
        self._all_dates = sorted(all_trade_dates)
        self._all_dates = [
            d for d in self._all_dates if self._start_date <= d <= self._end_date
        ]
        logger.info(f"Resampled: {len(self._all_dates)} {self._period} bars, {len(self._data)} stocks")

    def has_next(self) -> bool:
        return self._cursor < len(self._all_dates)

    def current_date(self) -> date:
        return self._all_dates[self._cursor] if self._cursor < len(self._all_dates) else self._end_date

    def next_day(self) -> dict[str, dict] | None:
        """Advance to next trading day, return {symbol: bar_dict} for all stocks with data."""
        if not self.has_next():
            return None

        current = self._all_dates[self._cursor]
        self._cursor += 1

        result: dict[str, dict] = {}
        for symbol, df in self._data.items():
            if current in df.index:
                row = df.loc[current]
                result[symbol] = {
                    "trade_date": current,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "amount": float(row["amount"]),
                }
        return result

    def get_window(self, symbol: str, as_of: date, lookback: int = 20) -> pd.DataFrame:
        """Return last `lookback` bars for symbol up to as_of (inclusive)."""
        df = self._data.get(symbol)
        if df is None or df.empty:
            return pd.DataFrame()
        return df[df.index <= as_of].tail(lookback)
