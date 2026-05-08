"""flags is_efetiva/is_falta/is_indefinida em fato_agenda

Decompõe o universo "não cancelado" (is_canceled=0) em três sub-categorias
baseadas em `status_type` do appointment:

- is_efetiva   → CHECKOUT (paciente atendido) — base correta para top
                 procedimentos, médicos, especialidades, mix
- is_falta     → MISSED (paciente faltou) — métrica clínica de absenteísmo
- is_indefinida→ status NULL e não cancelado — recepção não atualizou,
                 fica fora das métricas de eficiência

Antes desta migração `consultas_executadas` era `is_canceled=0` (865 em
abr/2026), que misturava efetivas (691) + faltas (75) + indefinidas (94)
+ confirmados sem desfecho (5). Mascarava o absenteísmo real.

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fato_agenda", sa.Column("is_efetiva", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("is_falta", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("is_indefinida", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index(
        "ix_fato_agenda_status_flags",
        "fato_agenda",
        ["tenant_id", "year_month_key", "is_efetiva", "is_falta"],
    )


def downgrade() -> None:
    op.drop_index("ix_fato_agenda_status_flags", table_name="fato_agenda")
    op.drop_column("fato_agenda", "is_indefinida")
    op.drop_column("fato_agenda", "is_falta")
    op.drop_column("fato_agenda", "is_efetiva")
