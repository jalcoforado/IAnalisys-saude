"""patients details (CC /patient/get)

Cria staging `stg_cc_patients_details` (payload completo do endpoint
`/patient/get` da Clinicorp) e adiciona `cpf` + `status` em
`core_patients` pra propagar dados do enriquecimento.

Endpoint validado em 2026-05-05. Retorna por paciente:
  PatientId, Name, Email, Phone, OtherDocumentId (CPF), Status, BirthDate

`birth_date` e `email` já existem em core_patients (eram populados como
None pela transform de eventos). Agora ganham fonte real.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── stg_cc_patients_details ──────────────────────────────────
    op.create_table(
        "stg_cc_patients_details",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_stg_cc_patients_details_external"),
    )

    # ── core_patients: cpf + status ──────────────────────────────
    op.add_column("core_patients", sa.Column("cpf", sa.String(14), nullable=True))
    op.add_column("core_patients", sa.Column("status", sa.String(20), nullable=True))
    op.create_index("ix_core_patients_cpf", "core_patients", ["tenant_id", "cpf"])


def downgrade() -> None:
    op.drop_index("ix_core_patients_cpf", table_name="core_patients")
    op.drop_column("core_patients", "status")
    op.drop_column("core_patients", "cpf")
    op.drop_table("stg_cc_patients_details")
