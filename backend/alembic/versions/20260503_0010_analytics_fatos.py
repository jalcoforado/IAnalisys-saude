"""analytics layer: fato_agenda + fato_orcamentos + fato_financeiro

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-03

Cria as 3 tabelas fato do star schema:
- fato_agenda      (de core_appointments — 1 linha por agendamento)
- fato_orcamentos  (de core_estimates — 1 linha por orçamento header)
- fato_financeiro  (de core_payments — 1 linha por pagamento)

Convenção: external_id = PK na origem (Clinicorp), permite JOIN lógico
com dim_paciente/dim_profissional/dim_tempo via patient_external_id /
professional_external_id / date_key.

Métricas oficiais que estes fatos destravam (docs/04_DATABASE_MODEL.md):
- Faturamento  = SUM(amount WHERE is_received=1) FROM fato_financeiro
- Conversão    = SUM(is_approved)/COUNT(*) FROM fato_orcamentos
- Absenteísmo  = SUM(is_canceled)/COUNT(*) FROM fato_agenda  (proxy)
- Ticket médio = faturamento / consultas
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _common_cols():
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("date_key", sa.Date(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("year_month_key", sa.String(7), nullable=True),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    # ── fato_agenda ──────────────────────────────────────────────
    op.create_table(
        "fato_agenda",
        *_common_cols(),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("professional_external_id", sa.BigInteger(), nullable=True),
        sa.Column("appointment_datetime", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("is_canceled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("category_description", sa.String(255), nullable=True),
        sa.Column("category_color", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_fato_agenda_external"),
    )
    op.create_index("ix_fato_agenda_date", "fato_agenda", ["tenant_id", "date_key"])
    op.create_index("ix_fato_agenda_year_month", "fato_agenda", ["tenant_id", "year_month_key"])
    op.create_index("ix_fato_agenda_patient", "fato_agenda", ["tenant_id", "patient_external_id"])
    op.create_index("ix_fato_agenda_professional", "fato_agenda", ["tenant_id", "professional_external_id"])

    # ── fato_orcamentos ──────────────────────────────────────────
    op.create_table(
        "fato_orcamentos",
        *_common_cols(),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("professional_external_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_rejected", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_followup", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("procedures_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_fato_orcamentos_external"),
    )
    op.create_index("ix_fato_orcamentos_date", "fato_orcamentos", ["tenant_id", "date_key"])
    op.create_index("ix_fato_orcamentos_year_month", "fato_orcamentos", ["tenant_id", "year_month_key"])
    op.create_index("ix_fato_orcamentos_status", "fato_orcamentos", ["tenant_id", "status"])

    # ── fato_financeiro ──────────────────────────────────────────
    op.create_table(
        "fato_financeiro",
        *_common_cols(),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("service_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("payment_form", sa.String(50), nullable=True),
        sa.Column("is_received", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_canceled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_fato_financeiro_external"),
    )
    op.create_index("ix_fato_financeiro_date", "fato_financeiro", ["tenant_id", "date_key"])
    op.create_index("ix_fato_financeiro_year_month", "fato_financeiro", ["tenant_id", "year_month_key"])
    op.create_index("ix_fato_financeiro_received", "fato_financeiro", ["tenant_id", "is_received"])
    op.create_index("ix_fato_financeiro_payment_form", "fato_financeiro", ["tenant_id", "payment_form"])


def downgrade() -> None:
    op.drop_table("fato_financeiro")
    op.drop_table("fato_orcamentos")
    op.drop_table("fato_agenda")
