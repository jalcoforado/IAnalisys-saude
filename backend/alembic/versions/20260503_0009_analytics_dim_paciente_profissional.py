"""analytics layer: dim_paciente + dim_profissional

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-03

Cria 2 dimensões usando core_* como fonte:
- dim_paciente:    materializa core_patients + colunas calculadas
                   (days_since_last_seen, is_active)
- dim_profissional: espelho de core_professionals

Padrão: PK BIGINT auto, UNIQUE(tenant_id, external_id) — sem FK rígida
para fatos (integridade lógica via external_id, decisão arquitetural
documentada no docs/07_ROADMAP.md).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── dim_paciente ─────────────────────────────────────────────
    op.create_table(
        "dim_paciente",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("mobile_phone", sa.String(50), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("days_since_last_seen", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_appointments", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_estimates", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_payments", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_dim_paciente_external"),
    )
    op.create_index("ix_dim_paciente_active", "dim_paciente", ["tenant_id", "is_active"])
    op.create_index("ix_dim_paciente_last_seen", "dim_paciente", ["tenant_id", "last_seen_at"])

    # ── dim_profissional ─────────────────────────────────────────
    op.create_table(
        "dim_profissional",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("cpf", sa.String(20), nullable=True),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_dim_profissional_external"),
    )


def downgrade() -> None:
    op.drop_table("dim_profissional")
    op.drop_table("dim_paciente")
