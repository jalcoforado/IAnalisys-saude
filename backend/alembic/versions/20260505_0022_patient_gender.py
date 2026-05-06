"""gender em core_patients e dim_paciente

API /patient/get pode retornar Gender (a confirmar). Fallback heurístico
por primeiro nome PT-BR no transform. Coluna char(1): 'M', 'F' ou NULL.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("core_patients", sa.Column("gender", sa.String(1), nullable=True))
    op.add_column("dim_paciente", sa.Column("gender", sa.String(1), nullable=True))


def downgrade() -> None:
    op.drop_column("dim_paciente", "gender")
    op.drop_column("core_patients", "gender")
