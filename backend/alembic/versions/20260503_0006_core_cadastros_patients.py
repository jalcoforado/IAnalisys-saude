"""core layer: cadastros estáticos + core_patients

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-03

Cria 9 tabelas core_*:
- 8 cadastros (1:1 com staging)
- 1 derivado (core_patients) — populado por extração de eventos

Convenções:
- PK: id BIGINT autoincrement
- Idempotência: UNIQUE(tenant_id, external_id)
- Sem FK rígida entre core_* (decisão arquitetural — ver docs/07_ROADMAP.md)
- Soft delete: is_deleted BOOLEAN
- Timestamps locais: created_at / updated_at (ON UPDATE CURRENT_TIMESTAMP)
- Timestamp da origem: external_updated_at (quando aplicável)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _common_columns():
    """Colunas comuns a toda tabela core_*."""
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
    ]


def _common_constraints(table_name: str):
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
    ]


def upgrade() -> None:
    # ── core_business ────────────────────────────────────────────
    op.create_table(
        "core_business",
        *_common_columns(),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("business_name", sa.String(255), nullable=True),
        sa.Column("company_id", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        *_common_constraints("core_business"),
    )

    # ── core_users_clinicorp ─────────────────────────────────────
    # Nome diferente de "core_users" para não confundir com users do auth
    op.create_table(
        "core_users_clinicorp",
        *_common_columns(),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        *_common_constraints("core_users_clinicorp"),
    )

    # ── core_professionals ───────────────────────────────────────
    op.create_table(
        "core_professionals",
        *_common_columns(),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("cpf", sa.String(20), nullable=True),
        *_common_constraints("core_professionals"),
    )

    # ── core_specialties ─────────────────────────────────────────
    op.create_table(
        "core_specialties",
        *_common_columns(),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("initial_id", sa.BigInteger(), nullable=True),
        sa.Column("related_characteristic_id", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        *_common_constraints("core_specialties"),
    )

    # ── core_procedures ──────────────────────────────────────────
    op.create_table(
        "core_procedures",
        *_common_columns(),
        sa.Column("internal_code", sa.String(50), nullable=True),
        sa.Column("procedure_name", sa.String(500), nullable=True),
        sa.Column("procedure_expertise_name", sa.String(255), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("price_list_id", sa.BigInteger(), nullable=True),
        sa.Column("price_list_name", sa.String(255), nullable=True),
        *_common_constraints("core_procedures"),
    )
    op.create_index(
        "ix_core_procedures_price_list", "core_procedures",
        ["tenant_id", "price_list_id"],
    )

    # ── core_appointment_categories ──────────────────────────────
    op.create_table(
        "core_appointment_categories",
        *_common_columns(),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        *_common_constraints("core_appointment_categories"),
    )

    # ── core_appointment_statuses ────────────────────────────────
    op.create_table(
        "core_appointment_statuses",
        *_common_columns(),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        *_common_constraints("core_appointment_statuses"),
    )

    # ── core_crm_campaigns ───────────────────────────────────────
    # external_id = Name (Clinicorp não tem id próprio aqui)
    op.create_table(
        "core_crm_campaigns",
        *_common_columns(),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_common_constraints("core_crm_campaigns"),
    )

    # ── core_patients ────────────────────────────────────────────
    # Derivado: extraído de PatientId em appointments + estimates + payments.
    # Populado por worker dedicado (patient_extractor) — não tem staging direto.
    op.create_table(
        "core_patients",
        *_common_columns(),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("mobile_phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("total_appointments", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_estimates", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_payments", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_common_constraints("core_patients"),
    )
    op.create_index(
        "ix_core_patients_last_seen", "core_patients",
        ["tenant_id", "last_seen_at"],
    )


def downgrade() -> None:
    for tbl in [
        "core_patients",
        "core_crm_campaigns",
        "core_appointment_statuses",
        "core_appointment_categories",
        "core_procedures",
        "core_specialties",
        "core_professionals",
        "core_users_clinicorp",
        "core_business",
    ]:
        op.drop_table(tbl)
