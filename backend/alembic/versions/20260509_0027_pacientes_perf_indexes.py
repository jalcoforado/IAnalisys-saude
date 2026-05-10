"""indexes p/ performance do dashboard /analise/pacientes

Antes desta migração:
- _top_ltv levava ~28s
- _para_resgatar levava ~22s
- TOTAL endpoint: 48s

Causa: JOIN dim_paciente × fato_financeiro usa
`CAST(dp.external_id AS UNSIGNED) = f.patient_external_id` (tipos incompatíveis
— VARCHAR vs BIGINT) e fato_financeiro NÃO tinha índice em patient_external_id,
forçando full-scan a cada paciente.

Indexes adicionados:
- fato_financeiro(tenant_id, patient_external_id, is_received) — cobre as
  agregações de LTV por paciente (Top LTV, Para Resgatar, novos_recorrentes)
- dim_paciente(tenant_id, days_since_last_seen) — cobre filtro de buckets de
  retenção (Para Resgatar, Saúde da Base)

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-09
"""
from alembic import op


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_fato_financeiro_patient",
        "fato_financeiro",
        ["tenant_id", "patient_external_id", "is_received"],
    )
    op.create_index(
        "ix_dim_paciente_days_last_seen",
        "dim_paciente",
        ["tenant_id", "days_since_last_seen"],
    )


def downgrade() -> None:
    op.drop_index("ix_dim_paciente_days_last_seen", table_name="dim_paciente")
    op.drop_index("ix_fato_financeiro_patient", table_name="fato_financeiro")
