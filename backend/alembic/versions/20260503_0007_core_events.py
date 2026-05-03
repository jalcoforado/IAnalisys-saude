"""core layer: eventos transacionais (appointments, estimates, payments, invoices, receipts, summary_entries)

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-03

Cria 7 tabelas core_* de eventos:
- core_appointments        (1:1 com staging)
- core_estimates           (header)
- core_estimate_procedures (line items, vindos do ProcedureList nested em raw_data)
- core_payments            (rico — pagador, treatment, datas múltiplas)
- core_invoices
- core_receipts
- core_summary_entries     (lançamentos contábeis CREDIT/DEBIT)

Sem FK rígida entre core_* — integridade lógica via external_id (decisão arquitetural).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _common_cols():
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
    ]


def _common_constraints(name: str):
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name=f"uk_{name}_external"),
    ]


def upgrade() -> None:
    # ── core_appointments ────────────────────────────────────────
    op.create_table(
        "core_appointments",
        *_common_cols(),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_name", sa.String(255), nullable=True),
        sa.Column("patient_email", sa.String(255), nullable=True),
        sa.Column("patient_mobile_phone", sa.String(50), nullable=True),
        sa.Column("professional_external_id", sa.BigInteger(), nullable=True),
        sa.Column("business_external_id", sa.BigInteger(), nullable=True),
        sa.Column("appointment_date", sa.DateTime(), nullable=True),
        sa.Column("from_time", sa.String(5), nullable=True),
        sa.Column("to_time", sa.String(5), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("category_description", sa.String(255), nullable=True),
        sa.Column("category_color", sa.String(20), nullable=True),
        sa.Column("procedures_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("alert_info", sa.Text(), nullable=True),
        sa.Column("schedule_to_id", sa.BigInteger(), nullable=True),
        sa.Column("was_edited", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_external_at", sa.DateTime(), nullable=True),
        sa.Column("created_external_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_external_user_name", sa.String(255), nullable=True),
        *_common_constraints("core_appointments"),
    )
    op.create_index("ix_core_appointments_date", "core_appointments", ["tenant_id", "appointment_date"])
    op.create_index("ix_core_appointments_professional", "core_appointments", ["tenant_id", "professional_external_id"])
    op.create_index("ix_core_appointments_patient", "core_appointments", ["tenant_id", "patient_external_id"])

    # ── core_estimates (header) ──────────────────────────────────
    op.create_table(
        "core_estimates",
        *_common_cols(),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_name", sa.String(255), nullable=True),
        sa.Column("patient_mobile_phone", sa.String(50), nullable=True),
        sa.Column("professional_external_id", sa.BigInteger(), nullable=True),
        sa.Column("professional_name", sa.String(255), nullable=True),
        sa.Column("business_external_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("estimate_date", sa.DateTime(), nullable=True),
        sa.Column("search_date", sa.DateTime(), nullable=True),
        sa.Column("created_external_at", sa.DateTime(), nullable=True),
        sa.Column("procedures_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_common_constraints("core_estimates"),
    )
    op.create_index("ix_core_estimates_date", "core_estimates", ["tenant_id", "estimate_date"])
    op.create_index("ix_core_estimates_patient", "core_estimates", ["tenant_id", "patient_external_id"])

    # ── core_estimate_procedures (line items) ────────────────────
    op.create_table(
        "core_estimate_procedures",
        *_common_cols(),
        sa.Column("treatment_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("dentist_external_id", sa.BigInteger(), nullable=True),
        sa.Column("dentist_name", sa.String(255), nullable=True),
        sa.Column("operation_description", sa.Text(), nullable=True),
        sa.Column("specialty_id", sa.BigInteger(), nullable=True),
        sa.Column("procedure_characteristic_id", sa.BigInteger(), nullable=True),
        sa.Column("related_characteristic_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("minimum_procedure_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("bill_type", sa.String(50), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("tooth", sa.String(50), nullable=True),
        sa.Column("surface", sa.String(50), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("payment_accounted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("payment_plan_id", sa.BigInteger(), nullable=True),
        sa.Column("price_id", sa.BigInteger(), nullable=True),
        sa.Column("price_list_id", sa.BigInteger(), nullable=True),
        sa.Column("status_id", sa.BigInteger(), nullable=True),
        sa.Column("status_description", sa.String(255), nullable=True),
        sa.Column("created_external_at", sa.DateTime(), nullable=True),
        *_common_constraints("core_estimate_procedures"),
    )
    op.create_index("ix_core_estimate_procedures_treatment", "core_estimate_procedures", ["tenant_id", "treatment_external_id"])
    op.create_index("ix_core_estimate_procedures_patient", "core_estimate_procedures", ["tenant_id", "patient_external_id"])

    # ── core_payments ────────────────────────────────────────────
    op.create_table(
        "core_payments",
        *_common_cols(),
        sa.Column("payment_header_external_id", sa.BigInteger(), nullable=True),
        sa.Column("treatment_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_name", sa.String(255), nullable=True),
        sa.Column("payer_name", sa.String(255), nullable=True),
        sa.Column("payer_email", sa.String(255), nullable=True),
        sa.Column("payer_phone", sa.String(50), nullable=True),
        sa.Column("payer_document", sa.String(20), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("service_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("interest_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("penalty_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("payment_form", sa.String(50), nullable=True),
        sa.Column("payment_form_characteristic_id", sa.BigInteger(), nullable=True),
        sa.Column("installment_number", sa.Integer(), nullable=True),
        sa.Column("installments_count", sa.Integer(), nullable=True),
        sa.Column("person_type", sa.String(50), nullable=True),
        sa.Column("payment_description", sa.Text(), nullable=True),
        sa.Column("receiver_business_external_id", sa.BigInteger(), nullable=True),
        sa.Column("is_received", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_canceled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("payment_date", sa.DateTime(), nullable=True),
        sa.Column("received_date", sa.DateTime(), nullable=True),
        sa.Column("confirmed_date", sa.DateTime(), nullable=True),
        sa.Column("check_out_date", sa.DateTime(), nullable=True),
        sa.Column("post_date", sa.DateTime(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("transaction_external_id", sa.String(128), nullable=True),
        *_common_constraints("core_payments"),
    )
    op.create_index("ix_core_payments_payment_date", "core_payments", ["tenant_id", "payment_date"])
    op.create_index("ix_core_payments_patient", "core_payments", ["tenant_id", "patient_external_id"])

    # ── core_invoices ────────────────────────────────────────────
    op.create_table(
        "core_invoices",
        *_common_cols(),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_name", sa.String(255), nullable=True),
        sa.Column("invoice_date", sa.DateTime(), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("is_received", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("installment_number", sa.Integer(), nullable=True),
        sa.Column("receiver_business_external_id", sa.BigInteger(), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        *_common_constraints("core_invoices"),
    )
    op.create_index("ix_core_invoices_date", "core_invoices", ["tenant_id", "invoice_date"])

    # ── core_receipts ────────────────────────────────────────────
    op.create_table(
        "core_receipts",
        *_common_cols(),
        sa.Column("reference_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("patient_external_id", sa.BigInteger(), nullable=True),
        sa.Column("patient_name", sa.String(255), nullable=True),
        sa.Column("receipt_date", sa.DateTime(), nullable=True),
        sa.Column("receiver_business_external_id", sa.BigInteger(), nullable=True),
        *_common_constraints("core_receipts"),
    )
    op.create_index("ix_core_receipts_date", "core_receipts", ["tenant_id", "receipt_date"])

    # ── core_summary_entries (lançamentos contábeis) ─────────────
    op.create_table(
        "core_summary_entries",
        *_common_cols(),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("month", sa.Integer(), nullable=True),
        sa.Column("entry_date", sa.DateTime(), nullable=True),
        sa.Column("post_date", sa.DateTime(), nullable=True),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("type", sa.String(20), nullable=True),  # CREDIT|DEBIT
        sa.Column("post_type", sa.String(50), nullable=True),
        sa.Column("entry_type", sa.String(50), nullable=True),
        sa.Column("related_book_entry_id", sa.BigInteger(), nullable=True),
        sa.Column("related_person_id", sa.BigInteger(), nullable=True),
        sa.Column("related_business_id", sa.BigInteger(), nullable=True),
        sa.Column("business_external_id", sa.BigInteger(), nullable=True),
        sa.Column("business_name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_entity", sa.String(50), nullable=True),
        sa.Column("reference_id_text", sa.String(255), nullable=True),
        sa.Column("additional_info", sa.Text(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_automated", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("person_id", sa.BigInteger(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("amount_before_discounts", sa.Numeric(12, 2), nullable=True),
        sa.Column("payment_form_characteristic_id", sa.BigInteger(), nullable=True),
        *_common_constraints("core_summary_entries"),
    )
    op.create_index("ix_core_summary_entries_date", "core_summary_entries", ["tenant_id", "entry_date"])
    op.create_index("ix_core_summary_entries_period", "core_summary_entries", ["tenant_id", "year", "month"])
    op.create_index("ix_core_summary_entries_type", "core_summary_entries", ["tenant_id", "type"])


def downgrade() -> None:
    for tbl in [
        "core_summary_entries",
        "core_receipts",
        "core_invoices",
        "core_payments",
        "core_estimate_procedures",
        "core_estimates",
        "core_appointments",
    ]:
        op.drop_table(tbl)
