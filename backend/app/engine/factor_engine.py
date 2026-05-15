"""Factor engine — compute factor values, layer backtest, IC analysis.

Built-in factors: reversal, momentum, volatility, volume, price patterns, trend.
All computations are look-ahead safe: features use only data through trade_date.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Built-in factor definitions
# ═══════════════════════════════════════════════════════════════

BUILTIN_FACTORS = [
    {
        "name": "reversal_5", "label": "5日反转",
        "category": "reversal", "description": "过去5日累计收益率，负向因子——涨多了短期回调",
        "params": {"period": 5},
    },
    {
        "name": "reversal_20", "label": "20日反转",
        "category": "reversal", "description": "过去20日累计收益率，负向因子",
        "params": {"period": 20},
    },
    {
        "name": "momentum_60_20", "label": "60日动量(跳过20日)",
        "category": "momentum", "description": "T-60到T-21的累计收益，正向因子——中期趋势延续",
        "params": {"skip": 20, "period": 40},
    },
    {
        "name": "volatility_20", "label": "20日波动率",
        "category": "volatility", "description": "20日收益率标准差，负向因子——低波动溢价",
        "params": {"period": 20},
    },
    {
        "name": "volume_ratio", "label": "量比",
        "category": "volume", "description": "当日成交量 / 20日均量",
        "params": {"period": 20},
    },
    {
        "name": "turnover_change", "label": "换手率变化",
        "category": "volume", "description": "换手率 / 20日均换手率",
        "params": {"period": 20},
    },
    {
        "name": "amplitude", "label": "振幅",
        "category": "price_pattern", "description": "(high-low)/close，日振幅",
        "params": {},
    },
    {
        "name": "upper_shadow_ratio", "label": "上影线占比",
        "category": "price_pattern", "description": "上影线长度/总振幅，抛压信号",
        "params": {},
    },
    {
        "name": "lower_shadow_ratio", "label": "下影线占比",
        "category": "price_pattern", "description": "下影线长度/总振幅，支撑信号",
        "params": {},
    },
    {
        "name": "ma_deviation_20", "label": "MA偏离度(20日)",
        "category": "trend", "description": "(收盘-MA20)/MA20，偏离均线程度",
        "params": {"period": 20},
    },
    {
        "name": "rsi_14", "label": "RSI(14)-50",
        "category": "trend", "description": "RSI相对强弱指标-50，超买超卖",
        "params": {"period": 14},
    },
    {
        "name": "boll_position", "label": "布林带位置",
        "category": "trend", "description": "(close-下轨)/(上轨-下轨)，在布林带中的相对位置",
        "params": {"period": 20},
    },
]


# ═══════════════════════════════════════════════════════════════
# Factor calculators
# ═══════════════════════════════════════════════════════════════

def _calc_reversal(df, period=5):
    """Past N-day return. Uses 'close' column."""
    if len(df) < period + 1:
        return np.nan
    prev_close = df.iloc[-(period + 1)]["close"]
    cur_close = df.iloc[-1]["close"]
    if prev_close == 0:
        return np.nan
    return (cur_close - prev_close) / prev_close


def _calc_momentum_skip(df, skip=20, period=40):
    """Return from T-(skip+period) to T-skip. Skips recent days."""
    need = skip + period + 1
    if len(df) < need:
        return np.nan
    start_close = df.iloc[-need]["close"]
    end_close = df.iloc[-(skip + 1)]["close"]
    if start_close == 0:
        return np.nan
    return (end_close - start_close) / start_close


def _calc_volatility(df, period=20):
    """Std of daily returns over N days."""
    if len(df) < period + 2:
        return np.nan
    closes = df["close"].values
    rets = np.diff(closes[-(period + 1):]) / closes[-(period + 1):-1]
    return float(np.std(rets))


def _calc_volume_ratio(df, period=20):
    """Today's volume / N-day avg volume."""
    if len(df) < period:
        return np.nan
    vols = df["volume"].values
    today_vol = vols[-1]
    avg_vol = np.mean(vols[-period:])
    if avg_vol == 0:
        return np.nan
    return today_vol / avg_vol


def _calc_turnover_change(df, period=20):
    """Turnover rate / N-day avg turnover."""
    if "turnover_rate" not in df.columns or len(df) < period:
        return np.nan
    turnovers = df["turnover_rate"].values
    today_t = turnovers[-1]
    avg_t = np.nanmean(turnovers[-period:])
    if avg_t == 0:
        return np.nan
    return today_t / avg_t


def _calc_amplitude(df):
    """(high - low) / close."""
    row = df.iloc[-1]
    if row["close"] == 0:
        return np.nan
    return (row["high"] - row["low"]) / row["close"]


def _calc_upper_shadow(df):
    """Upper shadow ratio."""
    row = df.iloc[-1]
    body_high = max(row["open"], row["close"])
    total_range = row["high"] - row["low"]
    if total_range == 0:
        return 0.0
    return (row["high"] - body_high) / total_range


def _calc_lower_shadow(df):
    """Lower shadow ratio."""
    row = df.iloc[-1]
    body_low = min(row["open"], row["close"])
    total_range = row["high"] - row["low"]
    if total_range == 0:
        return 0.0
    return (body_low - row["low"]) / total_range


def _calc_rsi(df, period=14):
    """RSI - 50. Wilder smoothing."""
    if len(df) < period + 2:
        return np.nan
    closes = df["close"].values
    deltas = np.diff(closes[-(period + 2):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 50.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi - 50.0


def _calc_ma_deviation(df, period=20):
    """(close - MA) / MA."""
    if len(df) < period:
        return np.nan
    ma = df["close"].values[-period:].mean()
    close = df.iloc[-1]["close"]
    if ma == 0:
        return np.nan
    return (close - ma) / ma


def _calc_boll_position(df, period=20):
    """Position within Bollinger Bands: (close-lower)/(upper-lower)."""
    if len(df) < period:
        return np.nan
    closes = df["close"].values[-period:]
    ma = np.mean(closes)
    std = np.std(closes)
    upper = ma + 2 * std
    lower = ma - 2 * std
    close = df.iloc[-1]["close"]
    if upper - lower == 0:
        return 0.5
    return (close - lower) / (upper - lower)


FACTOR_CALCULATORS: dict[str, Callable] = {
    "reversal_5": lambda df: _calc_reversal(df, period=5),
    "reversal_20": lambda df: _calc_reversal(df, period=20),
    "momentum_60_20": lambda df: _calc_momentum_skip(df, skip=20, period=40),
    "volatility_20": lambda df: _calc_volatility(df, period=20),
    "volume_ratio": lambda df: _calc_volume_ratio(df, period=20),
    "turnover_change": lambda df: _calc_turnover_change(df, period=20),
    "amplitude": _calc_amplitude,
    "upper_shadow_ratio": _calc_upper_shadow,
    "lower_shadow_ratio": _calc_lower_shadow,
    "ma_deviation_20": lambda df: _calc_ma_deviation(df, period=20),
    "rsi_14": lambda df: _calc_rsi(df, period=14),
    "boll_position": lambda df: _calc_boll_position(df, period=20),
}


# ═══════════════════════════════════════════════════════════════
# Factor Engine
# ═══════════════════════════════════════════════════════════════

@dataclass
class LayerBacktestResult:
    """Grouped backtest results for one day's factor values."""

    group_returns: dict[int, float] = field(default_factory=dict)  # group_idx → avg return
    ic_pearson: float = 0.0
    ic_spearman: float = 0.0
    stock_count: int = 0


def compute_layer_backtest(
    factor_values: dict[str, float],
    future_returns: dict[str, float],
    n_groups: int = 10,
) -> LayerBacktestResult:
    """One day's cross-sectional layer backtest.

    Args:
        factor_values: {stock_code: factor_value}
        future_returns: {stock_code: future_N_day_return}
        n_groups: number of groups (default 10)
    """
    result = LayerBacktestResult()

    # Align stocks — only keep those with both factor and future return
    common_stocks = set(factor_values.keys()) & set(future_returns.keys())
    if len(common_stocks) < n_groups * 2:
        result.stock_count = len(common_stocks)
        return result

    stocks = sorted(common_stocks)
    factors = np.array([factor_values[s] for s in stocks], dtype=float)
    rets = np.array([future_returns[s] for s in stocks], dtype=float)

    # Remove NaN
    valid = ~np.isnan(factors) & ~np.isnan(rets)
    factors = factors[valid]
    rets = rets[valid]
    result.stock_count = len(factors)

    if result.stock_count < n_groups * 2:
        return result

    # Rank and group
    ranks = stats.rankdata(factors)  # 1..N
    group_ids = np.floor((ranks - 1) / result.stock_count * n_groups).astype(int)
    group_ids = np.clip(group_ids, 0, n_groups - 1)

    for g in range(n_groups):
        mask = group_ids == g
        if mask.sum() > 0:
            result.group_returns[g] = float(np.mean(rets[mask]))
        else:
            result.group_returns[g] = 0.0

    # IC
    result.ic_pearson = float(stats.pearsonr(factors, rets)[0]) if result.stock_count > 2 else 0.0
    result.ic_spearman = float(stats.spearmanr(factors, rets)[0]) if result.stock_count > 2 else 0.0

    return result


def check_monotonicity(layer_returns: dict[int, float]) -> float:
    """Score how monotonic group returns are. 1 = perfect monotonic, 0 = random.

    Spearman rank correlation between group index and return.
    """
    groups = sorted(layer_returns.keys())
    rets = [layer_returns[g] for g in groups]
    if len(groups) < 3:
        return 0.0
    rho, _ = stats.spearmanr(range(len(groups)), rets)
    return abs(rho) if not np.isnan(rho) else 0.0
