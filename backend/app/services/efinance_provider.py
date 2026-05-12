"""efinance data provider — full implementation with cookie injection and rate limiting.

Key design:
- Monkey-patches efinance's EASTMONEY_REQUEST_HEADERS to inject ct cookie
- Rate-limits requests to avoid triggering EastMoney anti-bot measures
- Retries with exponential backoff on failures
- Converts efinance column names to our standard schema
"""

import logging
import time
import random
from typing import Optional

import pandas as pd

from app.services.data_provider import MarketDataProvider
from app.services.data_sync import normalize_code, clean_daily_bars

logger = logging.getLogger(__name__)

# ── Cookie injection ────────────────────────────

def inject_cookie(cookie_str: str):
    """Monkey-patch efinance's default request headers to include the ct cookie.

    Call this once at startup, before any data fetching.
    """
    import efinance.common.config as cfg
    cfg.EASTMONEY_REQUEST_HEADERS["Cookie"] = cookie_str
    # Also patch the futures config which has its own headers dict
    try:
        import efinance.futures.config as fcfg
        fcfg.EASTMONEY_REQUEST_HEADERS["Cookie"] = cookie_str
    except Exception:
        pass
    logger.info("efinance cookie injected successfully")


# ── Rate limiter ────────────────────────────────

class RateLimiter:
    """Simple rate limiter with jitter."""

    def __init__(self, min_interval: float = 0.5, jitter: float = 0.3):
        self.min_interval = min_interval
        self.jitter = jitter
        self._last_call = 0.0

    def wait(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            sleep_time = (self.min_interval - elapsed) + random.uniform(0, self.jitter)
            time.sleep(sleep_time)
        self._last_call = time.monotonic()


# Retry decorator (simple, no deps)
def with_retry(max_retries: int = 3, base_delay: float = 5.0):
    """Retry decorator with exponential backoff for EastMoney rate limiting."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    is_rate_limit = any(
                        kw in msg for kw in ["429", "too many", "限流", "访问过于频繁", "connection reset"]
                    )
                    if attempt < max_retries and is_rate_limit:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                        logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries + 1}), "
                            f"waiting {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    elif attempt < max_retries:
                        # Non-rate-limit error, retry once
                        delay = 2 + attempt
                        logger.warning(
                            f"Request failed (attempt {attempt + 1}): {e}, retrying in {delay}s"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed: {e}")
                        raise
            raise last_err
        return wrapper
    return decorator


# ── EfinanceProvider ────────────────────────────

class EfinanceProvider(MarketDataProvider):
    """efinance data source adapter — fetches from EastMoney via efinance library."""

    def __init__(self, cookie: str = ""):
        import efinance as ef
        self._ef = ef
        self._rate_limiter = RateLimiter(min_interval=0.5, jitter=0.3)

        # Inject cookie if provided
        if cookie:
            inject_cookie(cookie)

    # ── MarketDataProvider interface ────────────

    @with_retry(max_retries=3, base_delay=5.0)
    def get_instruments(self) -> pd.DataFrame:
        """Get all A-share stock basic info.

        Uses efinance's get_realtime_quotes to enumerate all stocks,
        then fetches base_info for each.
        """
        logger.info("Fetching A-share stock list from efinance...")
        try:
            # Get all real-time quotes to enumerate stocks
            df = self._ef.stock.get_realtime_quotes()
            if df is None or df.empty:
                raise ValueError("Got empty response from efinance get_realtime_quotes")

            # Rename columns to our standard
            col_map = {
                "股票代码": "code",
                "股票名称": "name",
                "市场编号": "exchange",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            # Normalize codes
            if "code" in df.columns:
                df["code"] = df["code"].astype(str).apply(normalize_code)

            # Map exchange codes: 1=SH, 0=SZ
            if "exchange" in df.columns:
                df["exchange"] = df["exchange"].apply(
                    lambda x: "SH" if str(x) == "1" else "SZ"
                )

            # Add missing columns
            if "status" not in df.columns:
                df["status"] = 1  # Assume active
            if "sector" not in df.columns:
                df["sector"] = "主板"

            logger.info(f"Fetched {len(df)} stocks from efinance")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            raise

    @with_retry(max_retries=3, base_delay=5.0)
    def get_daily_bars(
        self, symbol: str, start_date: Optional[str] = None,
        end_date: Optional[str] = None, adjust: Optional[str] = None
    ) -> pd.DataFrame:
        """Get daily OHLCV bars for a single stock.

        efinance.stock.get_quote_history returns all available history,
        we filter by date range afterward.
        """
        self._rate_limiter.wait()

        # Strip .SH/.SZ suffix — efinance uses plain 6-digit codes
        raw_code = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")

        logger.debug(f"Fetching daily bars for {raw_code}...")
        df = self._ef.stock.get_quote_history(raw_code)

        if df is None or df.empty:
            logger.warning(f"No data returned for {raw_code}")
            return pd.DataFrame()

        # Clean and standardize
        df = clean_daily_bars(df)

        # Filter by date range
        if start_date:
            df = df[df["trade_date"] >= pd.Timestamp(start_date).date()]
        if end_date:
            df = df[df["trade_date"] <= pd.Timestamp(end_date).date()]

        return df

    @with_retry(max_retries=3, base_delay=5.0)
    def get_base_info(self, symbol: str) -> dict:
        """Get basic info for a single stock."""
        self._rate_limiter.wait()

        raw_code = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        try:
            info = self._ef.stock.get_base_info(raw_code)
            if info is None:
                return {}
            if hasattr(info, "to_dict"):
                return info.to_dict()
            if isinstance(info, pd.Series):
                return info.to_dict()
            return info
        except Exception as e:
            logger.warning(f"Failed to get base info for {raw_code}: {e}")
            return {}

    @with_retry(max_retries=3, base_delay=5.0)
    def get_realtime_quotes(self) -> pd.DataFrame:
        """Get real-time quotes for all A-share stocks."""
        self._rate_limiter.wait()
        df = self._ef.stock.get_realtime_quotes()
        if df is not None and not df.empty:
            if "股票代码" in df.columns:
                df["股票代码"] = df["股票代码"].astype(str).apply(normalize_code)
        return df if df is not None else pd.DataFrame()

    # ── Abstract methods — implemented stubs ───

    def get_trade_calendar(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Trade calendar — not directly available from efinance.
        Will be generated from stock_daily distinct trade_date values.
        """
        raise NotImplementedError("Use local db to derive trade calendar")

    def get_minute_bars(self, symbol, start_date, end_date, freq='1min', adjust=None) -> pd.DataFrame:
        """Minute bars — not available via efinance free API."""
        raise NotImplementedError("Minute bars not available from efinance")

    def get_adjust_factors(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        """Adjust factors — efinance daily data is already forward-adjusted.
        We compute factors from raw close / adjusted close diffs.
        """
        raise NotImplementedError("Adjust factors to be derived from daily data")

    def get_suspensions(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Suspension records — can be derived from missing trade dates."""
        raise NotImplementedError("Suspensions derived from missing trade dates")

    def get_limit_prices(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        """Limit prices — computed from previous close * sector multiplier."""
        raise NotImplementedError("Limit prices computed locally")

    def get_index_members(self, index_code, date=None) -> pd.DataFrame:
        """Index members — not directly available."""
        raise NotImplementedError("Index members not available from efinance")

    def get_financials(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        """Financial statements."""
        raise NotImplementedError("Financial data not available from efinance")


# ── Batch helpers ───────────────────────────────

def batch_fetch_daily_bars(
    provider: EfinanceProvider,
    codes: list[str],
    on_progress=None,
    batch_size: int = 50,
    pause_between_batches: float = 5.0,
) -> pd.DataFrame:
    """Fetch daily bars for many stocks, with batching and pause.

    Args:
        provider: EfinanceProvider instance
        codes: List of stock codes (e.g. ['600000.SH', '000001.SZ'])
        on_progress: Optional callback(current, total)
        batch_size: Stocks per batch before pausing
        pause_between_batches: Seconds to pause between batches
    """
    all_data = []
    total = len(codes)

    for i in range(0, total, batch_size):
        batch = codes[i: i + batch_size]
        logger.info(f"Fetching batch {i // batch_size + 1}: stocks {i + 1}-{min(i + batch_size, total)}")

        for j, code in enumerate(batch):
            try:
                df = provider.get_daily_bars(code)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.error(f"Failed to fetch {code}: {e}")

            if on_progress:
                on_progress(i + j + 1, total)

        # Pause between batches to avoid rate limiting
        if i + batch_size < total:
            logger.info(f"Pausing {pause_between_batches}s between batches...")
            time.sleep(pause_between_batches)

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)
