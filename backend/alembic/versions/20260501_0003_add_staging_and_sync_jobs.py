"""add staging tables and sync_jobs

Revision ID: 20260501_0003
Revises: 20260501_0002
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── stg_appointments ─────────────────────────────────────
    op.create_table(
        "stg_appointments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_appointments_tenant_ref", "stg_appointments", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── stg_estimates ────────────────────────────────────────
    op.create_table(
        "stg_estimates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_estimates_tenant_ref", "stg_estimates", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── stg_cash_flow ────────────────────────────────────────
    op.create_table(
        "stg_cash_flow",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_cash_flow_tenant_ref", "stg_cash_flow", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── stg_payments ─────────────────────────────────────────
    op.create_table(
        "stg_payments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_payments_tenant_ref", "stg_payments", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── stg_analytics ────────────────────────────────────────
    op.create_table(
        "stg_analytics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_analytics_tenant_ref", "stg_analytics", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── stg_financial_summary ────────────────────────────────
    op.create_table(
        "stg_financial_summary",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_financial_summary_tenant_ref", "stg_financial_summary", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── stg_estimates_conversion ─────────────────────────────
    op.create_table(
        "stg_estimates_conversion",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("ref_date_from", sa.String(10), nullable=False),
        sa.Column("ref_date_to", sa.String(10), nullable=False),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stg_estimates_conversion_tenant_ref", "stg_estimates_conversion", ["tenant_id", "ref_date_from", "ref_date_to"])

    # ── sync_jobs ─────────────────────────────────────────────
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


def downgrade() -> None:
    op.drop_table("sync_jobs")
    op.drop_index("ix_stg_estimates_conversion_tenant_ref", table_name="stg_estimates_conversion")
    op.drop_table("stg_estimates_conversion")
    op.drop_index("ix_stg_financial_summary_tenant_ref", table_name="stg_financial_summary")
    op.drop_table("stg_financial_summary")
    op.drop_index("ix_stg_analytics_tenant_ref", table_name="stg_analytics")
    op.drop_table("stg_analytics")
    op.drop_index("ix_stg_payments_tenant_ref", table_name="stg_payments")
    op.drop_table("stg_payments")
    op.drop_index("ix_stg_cash_flow_tenant_ref", table_name="stg_cash_flow")
    op.drop_table("stg_cash_flow")
    op.drop_index("ix_stg_estimates_tenant_ref", table_name="stg_estimates")
    op.drop_table("stg_estimates")
    op.drop_index("ix_stg_appointments_tenant_ref", table_name="stg_appointments")
    op.drop_table("stg_appointments")
