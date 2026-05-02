"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="BRL"),
        sa.Column("ai_monthly_token_limit", sa.Integer(), nullable=False, server_default="100000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    # --- roles ---
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- user_tenants ---
    op.create_table(
        "user_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_tenants_user_id", "user_tenants", ["user_id"])
    op.create_index("ix_user_tenants_tenant_id", "user_tenants", ["tenant_id"])

    # Seed: papéis padrão definidos em docs/03_MULTI_TENANT_MODEL.md
    op.execute("""
        INSERT INTO roles (id, name, description) VALUES
        (UUID(), 'saas_admin',    'Administrador da plataforma SaaS'),
        (UUID(), 'tenant_admin',  'Administrador do tenant'),
        (UUID(), 'manager',       'Gestor da clínica'),
        (UUID(), 'financial',     'Responsável financeiro'),
        (UUID(), 'commercial',    'Responsável comercial'),
        (UUID(), 'operations',    'Responsável operacional')
    """)


def downgrade() -> None:
    op.drop_table("user_tenants")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("tenants")
