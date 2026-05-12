"""Backtest task and result models."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BacktestTask(Base):
    __tablename__ = "backtest_task"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    strategy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), comment="任务名称")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    stock_pool: Mapped[dict] = mapped_column(JSONB, default=dict, comment="股票池配置")
    initial_capital: Mapped[float] = mapped_column(
        Numeric(20, 4), default=1_000_000, comment="初始资金"
    )
    position_mode: Mapped[str] = mapped_column(
        String(20), default="fixed", comment="仓位模式"
    )
    benchmark: Mapped[str | None] = mapped_column(
        String(16), default="000300.SH", comment="基准指数"
    )
    adjust_mode: Mapped[str] = mapped_column(
        String(10), default="forward", comment="复权方式 forward/backward/none"
    )
    cost_config: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {"commission": 0.0003, "stamp_tax": 0.001, "transfer_fee": 0.000015},
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="pending/running/completed/failed"
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(100))
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度 0-100")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    total_return: Mapped[float] = mapped_column(Numeric(10, 4), comment="总收益率")
    total_return_amount: Mapped[float] = mapped_column(Numeric(20, 4), comment="总收益金额")
    annual_return: Mapped[float] = mapped_column(Numeric(10, 4), comment="年化收益率")
    benchmark_return: Mapped[float | None] = mapped_column(Numeric(10, 4), comment="基准收益率")
    excess_return: Mapped[float | None] = mapped_column(Numeric(10, 4), comment="超额收益")
    max_drawdown: Mapped[float] = mapped_column(Numeric(10, 4), comment="最大回撤")
    max_drawdown_days: Mapped[int | None] = mapped_column(Integer, comment="最大回撤周期天数")
    annual_volatility: Mapped[float] = mapped_column(Numeric(10, 4), comment="年化波动率")
    sharpe_ratio: Mapped[float] = mapped_column(Numeric(10, 4), comment="夏普比率")
    calmar_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), comment="卡尔马比率")
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), comment="索提诺比率")
    win_rate: Mapped[float] = mapped_column(Numeric(10, 4), comment="胜率")
    profit_loss_ratio: Mapped[float] = mapped_column(Numeric(10, 4), comment="盈亏比")
    trade_count: Mapped[int] = mapped_column(Integer, default=0, comment="总交易次数")
    avg_hold_days: Mapped[float | None] = mapped_column(Numeric(10, 2), comment="平均持仓天数")
    max_single_profit: Mapped[float | None] = mapped_column(Numeric(10, 4), comment="最大单笔盈利")
    max_single_loss: Mapped[float | None] = mapped_column(Numeric(10, 4), comment="最大单笔亏损")
    equity_curve: Mapped[dict | None] = mapped_column(JSONB, comment="资金曲线")
    drawdown_curve: Mapped[dict | None] = mapped_column(JSONB, comment="回撤曲线")
    monthly_returns: Mapped[dict | None] = mapped_column(JSONB, comment="月度收益")
    daily_returns: Mapped[dict | None] = mapped_column(JSONB, comment="日收益分布")


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(12), nullable=False)
    buy_date: Mapped[date] = mapped_column(Date, nullable=False)
    buy_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    buy_reason: Mapped[str | None] = mapped_column(Text, comment="买入原因")
    sell_date: Mapped[date] = mapped_column(Date, nullable=False)
    sell_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    sell_reason: Mapped[str | None] = mapped_column(Text, comment="卖出原因")
    quantity: Mapped[int] = mapped_column(Integer, default=100, comment="交易股数")
    hold_days: Mapped[int] = mapped_column(Integer, default=0)
    return_rate: Mapped[float] = mapped_column(Numeric(10, 4), comment="单笔收益率")
    return_amount: Mapped[float] = mapped_column(Numeric(20, 4), comment="单笔收益金额")
