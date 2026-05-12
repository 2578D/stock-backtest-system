"""Stock basic info model."""

from datetime import date

from sqlalchemy import Date, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, comment="代码 如 600000.SH")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="名称")
    exchange: Mapped[str] = mapped_column(String(8), nullable=False, comment="交易所 SH/SZ/BJ")
    list_date: Mapped[date | None] = mapped_column(Date, comment="上市日期")
    delist_date: Mapped[date | None] = mapped_column(Date, comment="退市日期")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="1=正常 0=退市")
    industry: Mapped[str | None] = mapped_column(String(128), comment="所属行业")
    sector: Mapped[str | None] = mapped_column(String(32), comment="板块 主板/创业板/科创板")
    is_st: Mapped[bool] = mapped_column(default=False, comment="是否ST")
