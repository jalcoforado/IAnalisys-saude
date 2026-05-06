"""core_appointment_tags + tag_class em fato_agenda

Tags do Clinicorp (`tags` no payload do appointment) são `AppointmentMarker`s
que o gestor aplica para sinalizar workflow operacional: "Aguardado vaga",
"Encaixe", "REMARCAR", "FINANCEIRO CONFERIDO", "CRC ORÇAMENTO - contatar" etc.

Cada appointment tem N tags. Modelamos como tabela child de appointments com
external_id próprio da tag (id global do Clinicorp).

A classificação semântica em `tag_class` é heurística por nome (igual category_group
em fato_agenda) e desnormalizada em `fato_agenda.has_*` flags pra agregação rápida.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "core_appointment_tags",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.CHAR(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("appointment_external_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("template_id", sa.String(64), nullable=True),
        sa.Column("tag_class", sa.String(20), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("external_updated_at", sa.DateTime, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.current_timestamp(),
            server_onupdate=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_appointment_tags_external"),
    )
    op.create_index(
        "ix_core_appointment_tags_appointment",
        "core_appointment_tags",
        ["tenant_id", "appointment_external_id"],
    )
    op.create_index(
        "ix_core_appointment_tags_class",
        "core_appointment_tags",
        ["tenant_id", "tag_class"],
    )

    # Flags em fato_agenda pra agregação rápida sem JOIN no hot path.
    # Replicam classes mais usadas — outras tags continuam acessíveis via JOIN.
    op.add_column("fato_agenda", sa.Column("has_waitlist", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("has_encaixe", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("has_remarcar", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("has_lembrete", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("has_orcamento_pendente", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("has_retorno_pendente", sa.Boolean, nullable=False, server_default="0"))
    op.add_column("fato_agenda", sa.Column("has_financeiro_conferido", sa.Boolean, nullable=False, server_default="0"))
    op.create_index(
        "ix_fato_agenda_has_waitlist",
        "fato_agenda",
        ["tenant_id", "date_key", "has_waitlist"],
    )


def downgrade() -> None:
    op.drop_index("ix_fato_agenda_has_waitlist", table_name="fato_agenda")
    op.drop_column("fato_agenda", "has_financeiro_conferido")
    op.drop_column("fato_agenda", "has_retorno_pendente")
    op.drop_column("fato_agenda", "has_orcamento_pendente")
    op.drop_column("fato_agenda", "has_lembrete")
    op.drop_column("fato_agenda", "has_remarcar")
    op.drop_column("fato_agenda", "has_encaixe")
    op.drop_column("fato_agenda", "has_waitlist")
    op.drop_index("ix_core_appointment_tags_class", table_name="core_appointment_tags")
    op.drop_index("ix_core_appointment_tags_appointment", table_name="core_appointment_tags")
    op.drop_table("core_appointment_tags")
