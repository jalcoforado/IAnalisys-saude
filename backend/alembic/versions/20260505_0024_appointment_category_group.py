"""category_group em fato_agenda

Catálogo Clinicorp tem 80+ categorias com nomes inconsistentes (CICATRIZADOR
repete 4x com cores diferentes, CONSULTA vs Consulta, etc). Pra insight útil
agrupamos em buckets semânticos: consulta / retorno / manutencao / procedimento
/ reabilitacao / ortodontia / bloqueio / outro.

A classificação é heurística por substring no SQL do build_fato_agenda — não
guarda em CORE pra não duplicar verdade. Desnormalizado em fato_agenda
exclusivamente pra agregações no hot path.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fato_agenda", sa.Column("category_group", sa.String(20), nullable=True))
    op.create_index("ix_fato_agenda_category_group", "fato_agenda", ["tenant_id", "date_key", "category_group"])


def downgrade() -> None:
    op.drop_index("ix_fato_agenda_category_group", table_name="fato_agenda")
    op.drop_column("fato_agenda", "category_group")
