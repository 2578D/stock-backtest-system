"""Strategy model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Strategy(Base):
    __tablename__ = "strategy"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(20), nullable=False, comment="visual / code")
    rules_json: Mapped[dict | None] = mapped_column(JSONB, comment="可视化策略JSON规则")
    code_content: Mapped[str | None] = mapped_column(Text, comment="代码策略内容")
    market: Mapped[str] = mapped_column(String(10), default="A股")
    period: Mapped[str] = mapped_column(String(10), default="daily")
    risk_control: Mapped[dict | None] = mapped_column(JSONB, comment="风控配置")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
