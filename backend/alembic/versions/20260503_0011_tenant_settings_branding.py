"""tenant settings — branding + dados da empresa

Adiciona colunas a `tenants` para suportar configuração white-label:
identidade visual (favicon, login_background, primary/secondary color)
e dados da empresa (CNPJ, endereço, contato).

`logo_url` já existia desde 0001 — apenas reaproveitamos.

Revision ID: 20260503_0011
Revises: 20260503_0010
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Identidade Visual ─────────────────────────────────────
    op.add_column("tenants", sa.Column("favicon_url", sa.String(500), nullable=True))
    op.add_column("tenants", sa.Column("login_background_url", sa.String(500), nullable=True))
    op.add_column("tenants", sa.Column("primary_color", sa.String(7), nullable=True))
    op.add_column("tenants", sa.Column("secondary_color", sa.String(7), nullable=True))

    # ── Dados da Empresa ──────────────────────────────────────
    op.add_column("tenants", sa.Column("legal_name", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("tax_id", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("phone", sa.String(50), nullable=True))
    op.add_column("tenants", sa.Column("whatsapp", sa.String(50), nullable=True))
    op.add_column("tenants", sa.Column("website", sa.String(255), nullable=True))

    # ── Endereço ──────────────────────────────────────────────
    op.add_column("tenants", sa.Column("address_zip", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("address_street", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("address_number", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("address_complement", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("address_district", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("address_city", sa.String(100), nullable=True))
    op.add_column("tenants", sa.Column("address_state", sa.String(2), nullable=True))


def downgrade() -> None:
    for col in (
        "address_state", "address_city", "address_district", "address_complement",
        "address_number", "address_street", "address_zip",
        "website", "whatsapp", "phone", "email", "tax_id", "legal_name",
        "secondary_color", "primary_color", "login_background_url", "favicon_url",
    ):
        op.drop_column("tenants", col)
