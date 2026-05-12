"""Data sync service — orchestrates data collection from external sources."""

import logging
from datetime import date, timedelta

import pandas as pd

from app.services.data_provider import MarketDataProvider

logger = logging.getLogger(__name__)


def normalize_code(raw_code: str) -> str:
    """标准化股票代码：600000 → 600000.SH"""
    raw_code = raw_code.strip()
    if "." in raw_code:
        return raw_code.upper()
    if raw_code.startswith(("6", "9")):
        return f"{raw_code}.SH"
    if raw_code.startswith(("0", "2", "3")):
        return f"{raw_code}.SZ"
    if raw_code.startswith(("4", "8")):
        return f"{raw_code}.BJ"
    return raw_code


def clean_daily_bars(df: pd.DataFrame) -> pd.DataFrame:
    """清洗并标准化日线行情数据."""
    if df.empty:
        return df

    # 字段映射：efinance 常见字段
    col_map = {
        "日期": "trade_date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "换手率": "turnover_rate",
        "股票代码": "code",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # 日期标准化
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    # 代码标准化
    if "code" in df.columns:
        df["code"] = df["code"].astype(str).apply(normalize_code)

    # 数值列清洗
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 去重
    dedup_cols = [c for c in ["code", "trade_date"] if c in df.columns]
    if dedup_cols:
        df = df.drop_duplicates(subset=dedup_cols, keep="last")

    # 过滤无效行
    required = ["open", "high", "low", "close"]
    df = df.dropna(subset=[c for c in required if c in df.columns])

    return df


def validate_daily_bars(df: pd.DataFrame) -> list[str]:
    """校验日线数据，返回问题列表."""
    warnings = []
    if df.empty:
        warnings.append("EMPTY_DATA: No records to validate")
        return warnings

    # OHLC 合法性
    if all(c in df.columns for c in ["low", "open", "close", "high"]):
        bad_ohlc = df[
            (df["low"] > df["open"])
            | (df["low"] > df["close"])
            | (df["high"] < df["open"])
            | (df["high"] < df["close"])
        ]
        if len(bad_ohlc) > 0:
            warnings.append(f"OHLC_VIOLATION: {len(bad_ohlc)} rows with invalid OHLC")

    # open 不能为 0
    if "open" in df.columns and (df["open"] <= 0).any():
        warnings.append("ZERO_OPEN: Found rows with open <= 0")

    # volume/amount >= 0
    for col in ["volume", "amount"]:
        if col in df.columns and (df[col] < 0).any():
            warnings.append(f"NEGATIVE_{col.upper()}: Found negative {col}")

    return warnings
