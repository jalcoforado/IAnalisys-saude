"""redesign staging: record-level dedup + sync_checkpoints + sync_jobs refactor

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-02

Mudanças principais:
- DROP das 7 tabelas stg_* antigas (snapshot por intervalo, sem dedup)
- DROP de sync_jobs antiga (schema mudou)
- CREATE de 15 tabelas stg_cc_* uniformes (record-level, idempotent via UK)
- CREATE de sync_checkpoints (controle de progresso por entidade)
- CREATE de sync_jobs nova (com entity, period DATE, métricas detalhadas)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


# Lista das 15 entidades de staging Clinicorp.
# Schema é uniforme — só o nome da tabela muda.
_STAGING_ENTITIES = [
    # Estáticas (sem período de referência)
    "business",
    "users",
    "professionals",
    "specialties",
    "procedures",
    "appointment_categories",
    "appointment_statuses",
    "crm_campaigns",
    # Transacionais (por período)
    "appointments",
    "estimates",
    "payments",
    "invoices",
    "receipts",
    "summary_entries",
    # Agregada (1 linha por mês com payload de 10 APIs)
    "kpis_monthly",
]


def upgrade() -> None:
    # ── DROP tabelas antigas ─────────────────────────────────────
    # As 7 stg_* originais (migration 0003) e sync_jobs original.
    # Estão vazias: o sync nunca rodou em produção.
    op.drop_table("stg_estimates_conversion")
    op.drop_table("stg_financial_summary")
    op.drop_table("stg_analytics")
    op.drop_table("stg_payments")
    op.drop_table("stg_cash_flow")
    op.drop_table("stg_estimates")
    op.drop_table("stg_appointments")
    op.drop_table("sync_jobs")

    # ── sync_jobs (recriada com schema novo) ─────────────────────
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),     # 'clinicorp', 'contaazul'
        sa.Column("entity", sa.String(50), nullable=False),     # 'business', 'appointments', ...
        sa.Column("status", sa.String(20), nullable=False),     # pending|running|success|error
        sa.Column("period_from", sa.Date(), nullable=True),     # NULL para syncs estáticos
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("records_fetched", sa.BigInteger(), nullable=True),
        sa.Column("records_inserted", sa.BigInteger(), nullable=True),
        sa.Column("records_updated", sa.BigInteger(), nullable=True),
        sa.Column("errors_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_jobs_tenant_entity", "sync_jobs", ["tenant_id", "entity", "created_at"])
    op.create_index("ix_sync_jobs_tenant_status", "sync_jobs", ["tenant_id", "status"])

    # ── sync_checkpoints ─────────────────────────────────────────
    # Controle de estado por (tenant, source, entity)
    op.create_table(
        "sync_checkpoints",
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("entity", sa.String(50), nullable=False),
        sa.Column("last_period_from", sa.Date(), nullable=True),
        sa.Column("last_period_to", sa.Date(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_job_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("total_records", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["last_sync_job_id"], ["sync_jobs.id"]),
        sa.PrimaryKeyConstraint("tenant_id", "source", "entity"),
    )

    # ── 15 tabelas stg_cc_* uniformes ────────────────────────────
    for entity in _STAGING_ENTITIES:
        table_name = f"stg_cc_{entity}"
        op.create_table(
            table_name,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
            sa.Column("external_id", sa.String(64), nullable=False),
            sa.Column("external_updated_at", sa.DateTime(), nullable=True),
            sa.Column("raw_data", mysql.JSON(), nullable=False),
            sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("sync_job_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
        )
        op.create_index(
            f"ix_{table_name}_updated",
            table_name,
            ["tenant_id", "external_updated_at"],
        )


def downgrade() -> None:
    # Drop staging novas
    for entity in reversed(_STAGING_ENTITIES):
        op.drop_table(f"stg_cc_{entity}")

    op.drop_table("sync_checkpoints")
    op.drop_table("sync_jobs")

    # Recria estado anterior (estrutura da migration 0003)
    # Apenas para permitir downgrade limpo. Schema antigo, sem dados.
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("records_fetched", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for legacy in [
        "stg_appointments", "stg_estimates", "stg_cash_flow", "stg_payments",
        "stg_analytics", "stg_financial_summary", "stg_estimates_conversion",
    ]:
        op.create_table(
            legacy,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
            sa.Column("ref_date_from", sa.String(10), nullable=False),
            sa.Column("ref_date_to", sa.String(10), nullable=False),
            sa.Column("raw_data", mysql.JSON(), nullable=False),
            sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{legacy}_tenant_ref", legacy, ["tenant_id", "ref_date_from", "ref_date_to"])
