"""analytics layer: dim_tempo (calendário)

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-03

Cria a primeira tabela da camada ANALYTICS: dim_tempo.

dim_tempo é uma dimensão de calendário com 1 linha por dia.
NÃO tem tenant_id porque calendário é universal (igual pra todo tenant).

Granularidades pré-calculadas pra acelerar GROUP BY em fatos:
- year, quarter, month, day, week (ISO)
- day_of_week (1=domingo .. 7=sábado, pra padrão MySQL DAYOFWEEK)
- year_month_key 'YYYY-MM' pra joins/agg mensal
- year_quarter_key 'YYYY-Q1..Q4'
- is_weekend, month_name_pt, day_of_week_name_pt
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dim_tempo",
        sa.Column("date_key", sa.Date(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),       # 1..4
        sa.Column("month", sa.Integer(), nullable=False),         # 1..12
        sa.Column("day", sa.Integer(), nullable=False),           # 1..31
        sa.Column("week", sa.Integer(), nullable=False),          # ISO week 1..53
        sa.Column("day_of_week", sa.Integer(), nullable=False),   # 1=dom .. 7=sáb
        sa.Column("day_of_year", sa.Integer(), nullable=False),   # 1..366
        sa.Column("year_month_key", sa.String(7), nullable=False),     # 'YYYY-MM'
        sa.Column("year_quarter_key", sa.String(7), nullable=False),   # 'YYYY-Q1'
        sa.Column("is_weekend", sa.Boolean(), nullable=False),
        sa.Column("month_name_pt", sa.String(20), nullable=False),         # 'Janeiro'
        sa.Column("day_of_week_name_pt", sa.String(20), nullable=False),   # 'Segunda'
        sa.PrimaryKeyConstraint("date_key"),
    )
    op.create_index("ix_dim_tempo_year_month", "dim_tempo", ["year", "month"])
    op.create_index("ix_dim_tempo_year_month_key", "dim_tempo", ["year_month_key"])
    op.create_index("ix_dim_tempo_year_quarter_key", "dim_tempo", ["year_quarter_key"])


def downgrade() -> None:
    op.drop_table("dim_tempo")
