"""user_home_layouts — persistência do "Meu IAnalisys" (My-Analisys) por usuário

Cria a tabela que guarda o layout customizado da home de cada usuário dentro de
um tenant. O JSON segue o contrato do react-grid-layout no frontend:

    [{"widget_id": "agenda_summary", "x": 0, "y": 0, "w": 1, "h": 1}, ...]

PK composta (tenant_id, user_id) — cada user tem um único layout por tenant.
Se nunca customizou, simplesmente não há linha (front aplica default da role).

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_home_layouts",
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("user_id", mysql.CHAR(36), nullable=False),
        sa.Column("layout_json", mysql.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", name="pk_user_home_layouts"),
    )


def downgrade() -> None:
    op.drop_table("user_home_layouts")
