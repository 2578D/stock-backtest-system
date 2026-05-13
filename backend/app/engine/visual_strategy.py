"""Visual strategy executor — interprets JSON rules at runtime.

Translates the visual strategy JSON format into real indicator calculations
and buy/sell signal generation. No code generation required.

JSON format:
{
  "buy": [
    {"defIndex": 0, "params": ["5"], "operator": ">", "threshold": "20"}
  ],
  "sell": [...],
  "risk": {"maxPositionRatio": 0.3, "maxHoldings": 10, "stopLoss": 0.08, "takeProfit": 0.15}
}

Indicator defIndex mapping (mirrors frontend VisualStrategyEditor.vue):
  0: MA    1: EMA    2: BOLL    3: MACD    4: RSI
  5: KDJ   6: 金叉    7: 死叉    8: 成交量   9: 换手率
  10: 涨跌幅  11: 收盘价
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from app.engine.strategy import IStrategy, Order, Portfolio, StrategyContext

logger = logging.getLogger(__name__)


@dataclass
class ConditionDef:
    """Compiled condition from JSON."""
    indicator: str
    params: list[float]
    operator: str
    threshold: float
    conjunction: str = "AND"  # "AND" | "OR"


@dataclass
class VisualStrategyConfig:
    """Parsed visual strategy configuration."""
    buy_conditions: list[ConditionDef] = field(default_factory=list)
    sell_conditions: list[ConditionDef] = field(default_factory=list)
    max_position_ratio: float = 0.3
    max_holdings: int = 10
    stop_loss: float = 0.08
    take_profit: float = 0.15
    fixed_amount: float = 50000.0  # fixed amount per buy


# ── Indicator registry ──────────────────────────

INDICATOR_NAMES = [
    "MA", "EMA", "BOLL", "MACD", "RSI",
    "KDJ", "金叉", "死叉", "成交量", "换手率",
    "涨跌幅", "收盘价",
]


def sma(data: list[float], period: int) -> float | None:
    if len(data) < period:
        return None
    return sum(data[-period:]) / period


def ema(data: list[float], period: int) -> float | None:
    if len(data) < period:
        return None
    k = 2.0 / (period + 1)
    e = sum(data[:period]) / period
    for v in data[period:]:
        e = v * k + e * (1 - k)
    return e


def stddev(data: list[float], period: int) -> float | None:
    if len(data) < period:
        return None
    w = data[-period:]
    m = sum(w) / period
    return math.sqrt(sum((x - m) ** 2 for x in w) / period)


def rsi(data: list[float], period: int) -> float | None:
    if len(data) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(data) - period, len(data)):
        diff = data[i] - data[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(data: list[float], fast: int, slow: int, signal: int) -> dict[str, float | None]:
    if len(data) < slow + signal:
        return {"dif": None, "dea": None, "hist": None}
    fast_ema = ema(data, fast)
    slow_ema = ema(data, slow)
    if fast_ema is None or slow_ema is None:
        return {"dif": None, "dea": None, "hist": None}
    dif = fast_ema - slow_ema

    # Compute DIF series for DEA
    dif_series: list[float] = []
    for i in range(slow - 1, len(data)):
        f = ema(data[:i + 1], fast)
        s = ema(data[:i + 1], slow)
        if f is not None and s is not None:
            dif_series.append(f - s)
    dea = ema(dif_series, signal) if len(dif_series) >= signal else None
    hist = (dif - dea) * 2 if dif is not None and dea is not None else None

    return {"dif": dif, "dea": dea, "hist": hist}


def kdj(data_high: list[float], data_low: list[float], data_close: list[float], period: int) -> dict[str, float | None]:
    if len(data_close) < period:
        return {"k": None, "d": None, "j": None}
    # RSV
    high_n = max(data_high[-period:])
    low_n = min(data_low[-period:])
    if high_n == low_n:
        rsv = 50.0
    else:
        rsv = (data_close[-1] - low_n) / (high_n - low_n) * 100.0
    return {"k": rsv, "d": rsv, "j": 3 * rsv - 2 * rsv}


def bollinger(data: list[float], period: int) -> dict[str, float | None]:
    if len(data) < period:
        return {"upper": None, "middle": None, "lower": None}
    mid = sma(data, period)
    sd = stddev(data, period)
    if mid is None or sd is None:
        return {"upper": None, "middle": None, "lower": None}
    return {"upper": mid + 2 * sd, "middle": mid, "lower": mid - 2 * sd}


# ── The strategy ────────────────────────────────

def parse_visual_rules(rules_json: dict) -> VisualStrategyConfig:
    """Parse frontend visual strategy JSON into engine config."""
    def map_cond(raw: dict) -> ConditionDef:
        idx = raw.get("defIndex", 0)
        return ConditionDef(
            indicator=INDICATOR_NAMES[idx] if idx < len(INDICATOR_NAMES) else "MA",
            params=[float(p) if p else 5.0 for p in raw.get("params", ["5"])],
            operator=raw.get("operator", ">"),
            threshold=float(raw.get("threshold", 0) or 0),
        )

    buy_raw = rules_json.get("buy", [])
    sell_raw = rules_json.get("sell", [])
    risk = rules_json.get("risk", {})

    return VisualStrategyConfig(
        buy_conditions=[map_cond(c) for c in buy_raw] if buy_raw else [],
        sell_conditions=[map_cond(c) for c in sell_raw] if sell_raw else [],
        max_position_ratio=float(risk.get("maxPositionRatio", 0.3)),
        max_holdings=int(risk.get("maxHoldings", 10)),
        stop_loss=float(risk.get("stopLoss", 0.08)),
        take_profit=float(risk.get("takeProfit", 0.15)),
    )


class VisualStrategy(IStrategy):
    """Strategy that evaluates visual JSON rules at runtime."""

    def __init__(self, config: VisualStrategyConfig | None = None):
        super().__init__()
        self._config = config or VisualStrategyConfig()
        self._bars: dict[str, list[dict]] = {}       # symbol → list of bars
        self._latest_bar: dict[str, dict] = {}        # symbol → current bar
        self._entry_price: dict[str, float] = {}      # symbol → avg entry price
        self._prev_indicators: dict[str, dict] = {}   # symbol → prev day indicator values
        self._today: date | None = None

    def set_config(self, config: VisualStrategyConfig) -> None:
        self._config = config

    def on_init(self, context: StrategyContext) -> None:
        self._bars = {}
        self._latest_bar = {}
        self._entry_price = {}
        self._prev_indicators = {}

    def on_bar(
        self,
        context: StrategyContext,
        bar: dict[str, float | int],
        portfolio: Portfolio,
    ) -> list[Order]:
        symbol = bar.get("code") or bar.get("symbol", "")
        if not symbol:
            return []

        # Track bars
        if symbol not in self._bars:
            self._bars[symbol] = []
        self._bars[symbol].append(bar)
        self._latest_bar[symbol] = bar

        orders: list[Order] = []

        # Compute indicators for this symbol
        ind = self._compute_indicators(symbol)
        prev_ind = self._prev_indicators.get(symbol, {})

        # Check for sell signals first (risk management + sell conditions)
        if symbol in portfolio.positions:
            pos = portfolio.positions[symbol]
            if pos.quantity > 0:
                # Stop loss / take profit
                price = bar.get("close", 0)
                entry = self._entry_price.get(symbol, pos.avg_cost or price)
                if entry > 0:
                    pnl_pct = (price - entry) / entry
                    if pnl_pct <= -self._config.stop_loss:
                        orders.append(Order(
                            symbol, "sell", pos.quantity, price,
                            f"止损 {pnl_pct*100:.2f}%",
                        ))
                        return orders
                    if pnl_pct >= self._config.take_profit:
                        orders.append(Order(
                            symbol, "sell", pos.quantity, price,
                            f"止盈 {pnl_pct*100:.2f}%",
                        ))
                        return orders

                # Check sell conditions
                if self._eval_conditions(self._config.sell_conditions, symbol, ind, prev_ind):
                    orders.append(Order(
                        symbol, "sell", pos.quantity, price,
                        "卖出信号",
                    ))
                    return orders

        # Check buy conditions (only if not already holding)
        if symbol not in portfolio.positions or portfolio.positions[symbol].quantity == 0:
            if self._eval_conditions(self._config.buy_conditions, symbol, ind, prev_ind):
                # Calculate position size
                price = bar.get("close", 0)
                if price <= 0:
                    return orders

                max_value = portfolio.total_value * self._config.max_position_ratio
                # Count current holdings
                current_holdings = sum(
                    1 for p in portfolio.positions.values() if p.quantity > 0
                )
                if current_holdings >= self._config.max_holdings:
                    return orders

                qty = int(min(
                    self._config.fixed_amount / price,
                    max_value / price,
                ))
                if qty >= 100:  # A-share minimum lot is 100 shares
                    qty = (qty // 100) * 100
                    self._entry_price[symbol] = price
                    orders.append(Order(
                        symbol, "buy", qty, price,
                        "买入信号",
                    ))

        # Store indicators for cross-detection next day
        self._prev_indicators[symbol] = ind

        return orders

    def _compute_indicators(self, symbol: str) -> dict:
        """Compute all indicators that are referenced in conditions."""
        bars = self._bars.get(symbol, [])
        if not bars:
            return {}

        closes = [float(b.get("close", 0)) for b in bars]
        highs = [float(b.get("high", 0)) for b in bars]
        lows = [float(b.get("low", 0)) for b in bars]
        volumes = [float(b.get("volume", 0)) for b in bars]
        turnovers = [float(b.get("turnover_rate", 0)) for b in bars]

        # Collect all parameter sets needed
        result: dict[str, Any] = {}
        all_conds = self._config.buy_conditions + self._config.sell_conditions
        computed: set[tuple] = set()

        for c in all_conds:
            key = (c.indicator, tuple(c.params))
            if key in computed:
                continue
            computed.add(key)

            name = c.indicator
            params = c.params

            if name == "MA":
                result[f"MA({params[0]:.0f})"] = sma(closes, int(params[0]))
            elif name == "EMA":
                result[f"EMA({params[0]:.0f})"] = ema(closes, int(params[0]))
            elif name == "BOLL":
                p = int(params[0])
                b = bollinger(closes, p)
                result[f"BOLL_upper({p})"] = b["upper"]
                result[f"BOLL_mid({p})"] = b["middle"]
                result[f"BOLL_lower({p})"] = b["lower"]
            elif name == "MACD":
                fast, slow, sig = int(params[0]), int(params[1]), int(params[2])
                m = macd(closes, fast, slow, sig)
                result[f"MACD_dif({fast},{slow})"] = m["dif"]
                result[f"MACD_dea({fast},{slow})"] = m["dea"]
                result[f"MACD_hist({fast},{slow})"] = m["hist"]
            elif name == "RSI":
                result[f"RSI({params[0]:.0f})"] = rsi(closes, int(params[0]))
            elif name == "KDJ":
                p = int(params[0])
                k = kdj(highs, lows, closes, p)
                result[f"KDJ_k({p})"] = k["k"]
                result[f"KDJ_d({p})"] = k["d"]
                result[f"KDJ_j({p})"] = k["j"]
            elif name == "金叉":
                fast_p, slow_p = int(params[0]), int(params[1])
                result[f"MA({fast_p})"] = sma(closes, fast_p)
                result[f"MA({slow_p})"] = sma(closes, slow_p)
            elif name == "死叉":
                fast_p, slow_p = int(params[0]), int(params[1])
                result[f"MA({fast_p})"] = sma(closes, fast_p)
                result[f"MA({slow_p})"] = sma(closes, slow_p)
            elif name == "成交量":
                result["volume"] = volumes[-1] if volumes else None
                result["volume_ma5"] = sma(volumes, 5)
            elif name == "换手率":
                result["turnover"] = turnovers[-1] if turnovers else None
            elif name == "涨跌幅":
                if len(closes) >= 2:
                    result["change_pct"] = (closes[-1] - closes[-2]) / closes[-2] * 100
            elif name == "收盘价":
                result["close"] = closes[-1] if closes else None

        return result

    def _eval_conditions(
        self,
        conditions: list[ConditionDef],
        symbol: str,
        indicators: dict,
        prev_indicators: dict,
    ) -> bool:
        """Evaluate all conditions. AND logic between conditions."""
        if not conditions:
            return False

        results = []
        for c in conditions:
            results.append(self._eval_single(c, indicators, prev_indicators))

        # All conditions must be true (AND logic)
        return all(results) if results else False

    def _eval_single(
        self,
        cond: ConditionDef,
        indicators: dict,
        prev_indicators: dict,
    ) -> bool:
        """Evaluate a single condition."""
        name = cond.indicator
        params = cond.params
        op = cond.operator
        threshold = cond.threshold

        # Build indicator key and get value
        if name in ("MA", "EMA", "RSI"):
            key = f"{name}({params[0]:.0f})"
            val = indicators.get(key)
            prev_val = prev_indicators.get(key)
        elif name == "BOLL":
            p = int(params[0])
            val = indicators.get(f"BOLL_mid({p})")
            # For BOLL, use close vs upper/mid/lower
            close = indicators.get("close") or self._latest_bar.get(symbol, {}).get("close", 0)
            # Which band? default upper
            val = indicators.get(f"BOLL_upper({p})")
        elif name == "MACD":
            fast, slow = int(params[0]), int(params[1])
            val = indicators.get(f"MACD_dif({fast},{slow})")
            prev_val = prev_indicators.get(f"MACD_dif({fast},{slow})")
            dea = indicators.get(f"MACD_dea({fast},{slow})")
            prev_dea = prev_indicators.get(f"MACD_dea({fast},{slow})")
        elif name == "KDJ":
            p = int(params[0])
            val = indicators.get(f"KDJ_k({p})")
            prev_val = prev_indicators.get(f"KDJ_k({p})")
        elif name in ("金叉", "死叉"):
            fast_p, slow_p = int(params[0]), int(params[1])
            fast_key = f"MA({fast_p})"
            slow_key = f"MA({slow_p})"
            val = indicators.get(fast_key)
            slow_val = indicators.get(slow_key)
            prev_val = prev_indicators.get(fast_key)
            prev_slow_val = prev_indicators.get(slow_key)
        elif name == "成交量":
            val = indicators.get("volume")
            vol_ma = indicators.get("volume_ma5")
        elif name == "换手率":
            val = indicators.get("turnover")
        elif name == "涨跌幅":
            val = indicators.get("change_pct")
        elif name == "收盘价":
            val = indicators.get("close")
        else:
            return False

        if val is None:
            return False

        # Evaluate operator
        if op == ">":
            return float(val) > float(threshold)
        elif op == "<":
            return float(val) < float(threshold)
        elif op == ">=":
            return float(val) >= float(threshold)
        elif op == "<=":
            return float(val) <= float(threshold)
        elif op == "cross_above":
            if prev_val is None:
                return False
            if name == "金叉":
                return prev_val <= prev_slow_val and val > slow_val
            # MACD DIF crosses above DEA
            if name == "MACD":
                return prev_val <= prev_dea and val > dea
            return False
        elif op == "cross_below":
            if prev_val is None:
                return False
            if name == "死叉":
                return prev_val >= prev_slow_val and val < slow_val
            if name == "MACD":
                return prev_val >= prev_dea and val < dea
            return False

        return False
