"""staging ca categorias + centros de custo

Adiciona 2 tabelas STAGING para os endpoints `/v1/categorias` e
`/v1/centro-de-custo` do Conta Azul. Necessárias pro CORE financeiro:
parcelas trazem `categorias[]` e `centros_custo[]` inline (id+nome),
mas a tabela mestre dá o cadastro completo (DRE, hierarquia pai/filho,
tipo RECEITA/DESPESA).

Padrão idêntico às outras stg_ca_* (migration 0015).

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


_STG_ENTITIES = ["categorias", "centros_custo"]


def upgrade() -> None:
    for entity in _STG_ENTITIES:
        table_name = f"stg_ca_{entity}"
        op.create_table(
            table_name,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
            sa.Column("external_id", sa.String(64), nullable=False),
            sa.Column("external_updated_at", sa.DateTime(), nullable=True),
            sa.Column("raw_data", mysql.JSON(), nullable=False),
            sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("sync_job_id", sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
        )
        op.create_index(
            f"ix_{table_name}_updated",
            table_name,
            ["tenant_id", "external_updated_at"],
        )


def downgrade() -> None:
    for entity in reversed(_STG_ENTITIES):
        op.drop_table(f"stg_ca_{entity}")
