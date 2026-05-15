"""Factor research models — factor definitions, daily values, analysis results."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FactorDefinition(Base):
    """Factor metadata — formula, category, parameters."""

    __tablename__ = "factor_definition"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="因子标识")
    label: Mapped[str] = mapped_column(String(64), nullable=False, comment="显示名")
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="分类: reversal/momentum/volatility/volume/price_pattern/trend"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="因子说明")
    formula: Mapped[str | None] = mapped_column(Text, comment="计算公式或代码")
    params: Mapped[dict] = mapped_column(JSONB, default=dict, comment="参数 JSON")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, comment="内置因子")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FactorValue(Base):
    """Daily factor value per stock."""

    __tablename__ = "factor_value"
    __table_args__ = (
        UniqueConstraint("factor_id", "stock_code", "trade_date", name="uq_factor_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, comment="因子值")
    rank_pct: Mapped[float | None] = mapped_column(Float, comment="截面百分位 0-100")


class FactorAnalysis(Base):
    """Factor analysis results — IC series, layer returns, etc."""

    __tablename__ = "factor_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    factor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    group_count: Mapped[int] = mapped_column(Integer, default=10, comment="分组数")
    forward_days: Mapped[int] = mapped_column(Integer, default=10, comment="未来N天")
    ic_mean: Mapped[float | None] = mapped_column(Float, comment="IC均值")
    ic_std: Mapped[float | None] = mapped_column(Float, comment="IC标准差")
    icir: Mapped[float | None] = mapped_column(Float, comment="信息比率")
    ic_series: Mapped[dict | None] = mapped_column(JSONB, comment="IC序列 date→ic")
    layer_returns: Mapped[dict | None] = mapped_column(JSONB, comment="分层收益 {group: avg_return}")
    layer_cumulative: Mapped[dict | None] = mapped_column(JSONB, comment="分层累计收益 {group: {date: cum_return}}")
    monotonicity: Mapped[float | None] = mapped_column(Float, comment="分层单调性得分")
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending/running/completed/failed"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
