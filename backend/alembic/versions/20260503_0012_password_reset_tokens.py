"""password reset tokens

Tabela para armazenar tokens de recuperação de senha. Guardamos apenas
o SHA-256 do token (nunca o raw) — quando o usuário clica no link do
email, hash do token recebido é comparado com o armazenado.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Index("ix_password_reset_user", "user_id"),
        sa.Index("ix_password_reset_expires", "expires_at"),
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
