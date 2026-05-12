"""Data source provider abstract interface and efinance implementation."""

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    """外部数据源统一接口 — 所有 Provider 必须实现此接口"""

    @abstractmethod
    def get_trade_calendar(self, start_date=None, end_date=None) -> pd.DataFrame:
        """获取交易日历"""
        ...

    @abstractmethod
    def get_instruments(self) -> pd.DataFrame:
        """获取股票基础信息"""
        ...

    @abstractmethod
    def get_daily_bars(
        self, symbol, start_date, end_date, adjust=None
    ) -> pd.DataFrame:
        """获取日线行情"""
        ...

    @abstractmethod
    def get_adjust_factors(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        """获取复权因子"""
        ...

    @abstractmethod
    def get_suspensions(self, start_date=None, end_date=None) -> pd.DataFrame:
        """获取停牌记录"""
        ...

    @abstractmethod
    def get_limit_prices(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        """获取涨跌停价格"""
        ...

    @abstractmethod
    def get_index_members(self, index_code, date=None) -> pd.DataFrame:
        """获取指数成分股"""
        ...


class EfinanceProvider(MarketDataProvider):
    """efinance 数据源适配器 — 当前首个落地实现"""

    def __init__(self):
        import efinance as ef
        self._ef = ef
        self._request_interval = 0.5  # 限流间隔秒

    def get_trade_calendar(self, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("efinance trade calendar — TODO")

    def get_instruments(self) -> pd.DataFrame:
        raise NotImplementedError("efinance instruments — TODO")

    def get_daily_bars(
        self, symbol, start_date, end_date, adjust=None
    ) -> pd.DataFrame:
        raise NotImplementedError("efinance daily bars — TODO")

    def get_adjust_factors(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("efinance adjust factors — TODO")

    def get_suspensions(self, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("efinance suspensions — TODO")

    def get_limit_prices(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("efinance limit prices — TODO")

    def get_index_members(self, index_code, date=None) -> pd.DataFrame:
        raise NotImplementedError("efinance index members — TODO")


class LocalWarehouseProvider(MarketDataProvider):
    """本地标准库数据提供者 — 唯一供回测引擎消费的 Provider"""

    def __init__(self, db_session_factory):
        self._db = db_session_factory

    def get_trade_calendar(self, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("Local trade calendar — TODO")

    def get_instruments(self) -> pd.DataFrame:
        raise NotImplementedError("Local instruments — TODO")

    def get_daily_bars(
        self, symbol, start_date, end_date, adjust=None
    ) -> pd.DataFrame:
        raise NotImplementedError("Local daily bars — TODO")

    def get_adjust_factors(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("Local adjust factors — TODO")

    def get_suspensions(self, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("Local suspensions — TODO")

    def get_limit_prices(self, symbol, start_date=None, end_date=None) -> pd.DataFrame:
        raise NotImplementedError("Local limit prices — TODO")

    def get_index_members(self, index_code, date=None) -> pd.DataFrame:
        raise NotImplementedError("Local index members — TODO")


# Provider registry
_providers: dict[str, MarketDataProvider] = {}


def register_provider(name: str, provider: MarketDataProvider):
    _providers[name] = provider


def get_provider(name: str) -> MarketDataProvider:
    if name not in _providers:
        raise ValueError(f"Unknown provider: {name}")
    return _providers[name]
