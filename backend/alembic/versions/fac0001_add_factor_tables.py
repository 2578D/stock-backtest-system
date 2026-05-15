"""add factor tables

Revision ID: fac0001
Revises:
Create Date: 2026-05-15

Factor research tables: factor_definition, factor_value, factor_analysis.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "fac0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "factor_definition",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False, comment="因子标识"),
        sa.Column("label", sa.String(64), nullable=False, comment="显示名"),
        sa.Column("category", sa.String(32), nullable=False, comment="分类"),
        sa.Column("description", sa.Text(), comment="因子说明"),
        sa.Column("formula", sa.Text(), comment="计算公式"),
        sa.Column("params", postgresql.JSONB(), default=dict, comment="参数JSON"),
        sa.Column("is_builtin", sa.Boolean(), default=True, comment="内置因子"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "factor_value",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("factor_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("stock_code", sa.String(12), nullable=False, index=True),
        sa.Column("trade_date", sa.Date(), nullable=False, index=True),
        sa.Column("value", sa.Float(), comment="因子值"),
        sa.Column("rank_pct", sa.Float(), comment="截面百分位"),
        sa.UniqueConstraint("factor_id", "stock_code", "trade_date", name="uq_factor_value"),
    )

    op.create_table(
        "factor_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("factor_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("group_count", sa.Integer(), default=10, comment="分组数"),
        sa.Column("forward_days", sa.Integer(), default=10, comment="未来N天"),
        sa.Column("ic_mean", sa.Float(), comment="IC均值"),
        sa.Column("ic_std", sa.Float(), comment="IC标准差"),
        sa.Column("icir", sa.Float(), comment="信息比率"),
        sa.Column("ic_series", postgresql.JSONB(), comment="IC序列"),
        sa.Column("layer_returns", postgresql.JSONB(), comment="分层收益"),
        sa.Column("layer_cumulative", postgresql.JSONB(), comment="分层累计收益"),
        sa.Column("monotonicity", sa.Float(), comment="分层单调性"),
        sa.Column("status", sa.String(20), default="pending", comment="状态"),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("factor_analysis")
    op.drop_table("factor_value")
    op.drop_table("factor_definition")
