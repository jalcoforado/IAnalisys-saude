"""campos de origem em core_appointments

Promove `HowDidMeet` e `IndicationSource` do raw_data (stg_cc_appointments)
para colunas tipadas em core_appointments. Usado pela tela
/pacientes/captacao (Frente A — Captura de origem).

Cobertura atual em Parente: 22 de 20.753 appointments com HowDidMeet
preenchido (0,11%) — exatamente o "choque visual" que motiva a tela.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("core_appointments", sa.Column("how_did_meet", sa.String(100), nullable=True))
    op.add_column("core_appointments", sa.Column("indication_source", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("core_appointments", "indication_source")
    op.drop_column("core_appointments", "how_did_meet")
