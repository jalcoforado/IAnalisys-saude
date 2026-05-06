"""dim_paciente PII (email, birth_date, cpf)

Adiciona campos de PII na dim_paciente que vêm do enriquecimento via
/patient/get (sub-PR 18). Idade não é armazenada — calculada
dinamicamente no frontend via birth_date pra evitar staleness.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dim_paciente", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("dim_paciente", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("dim_paciente", sa.Column("cpf", sa.String(14), nullable=True))


def downgrade() -> None:
    op.drop_column("dim_paciente", "cpf")
    op.drop_column("dim_paciente", "birth_date")
    op.drop_column("dim_paciente", "email")
