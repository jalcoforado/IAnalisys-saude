"""appointment status_id em core_appointments e fato_agenda

Propaga StatusId do Clinicorp pra CORE e ANALYTICS. Permite distinguir
Confirmado/Em espera/Atendido/Atrasado/Faltou na agenda — base pra
indicador visual na matriz, insights ao vivo e predição de no-show.

`status_type` é o enum Clinicorp (CONFIRMED, ARRIVED, IN_SESSION,
CHECKOUT, MISSED, LATE, CALL, PENDING_MATERIAL) — preferimos sobre o
nome localizado por ser estável entre tenants.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # core_appointments — guarda apenas o status_id; o resto é JOIN.
    op.add_column("core_appointments", sa.Column("status_id", sa.BigInteger(), nullable=True))
    op.create_index("ix_core_appointments_status", "core_appointments", ["tenant_id", "status_id"])

    # fato_agenda — desnormaliza pra evitar JOIN no hot path da agenda.
    op.add_column("fato_agenda", sa.Column("status_id", sa.BigInteger(), nullable=True))
    op.add_column("fato_agenda", sa.Column("status_type", sa.String(50), nullable=True))
    op.add_column("fato_agenda", sa.Column("status_description", sa.String(100), nullable=True))
    op.add_column("fato_agenda", sa.Column("status_color", sa.String(20), nullable=True))
    op.create_index("ix_fato_agenda_status_type", "fato_agenda", ["tenant_id", "date_key", "status_type"])


def downgrade() -> None:
    op.drop_index("ix_fato_agenda_status_type", table_name="fato_agenda")
    op.drop_column("fato_agenda", "status_color")
    op.drop_column("fato_agenda", "status_description")
    op.drop_column("fato_agenda", "status_type")
    op.drop_column("fato_agenda", "status_id")
    op.drop_index("ix_core_appointments_status", table_name="core_appointments")
    op.drop_column("core_appointments", "status_id")
