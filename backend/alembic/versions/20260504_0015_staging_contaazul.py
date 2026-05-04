"""staging conta azul

Cria 6 tabelas STAGING `stg_ca_*` espelhando os endpoints reais da API
Conta Azul (validados em smoke-test 2026-05-04). Padrão idêntico ao
Clinicorp (migration 0005): id sintético + UNIQUE (tenant_id, external_id)
pra idempotência via INSERT...ON DUPLICATE KEY UPDATE.

Entidades:
  - stg_ca_pessoas              (clientes + fornecedores em uma só)
  - stg_ca_produtos
  - stg_ca_servicos
  - stg_ca_vendedores
  - stg_ca_contas_receber       (eventos financeiros — entrada)
  - stg_ca_contas_pagar         (eventos financeiros — saída)

Convenção: `external_id` = UUID retornado pelo Conta Azul.
`external_updated_at` recebe `data_alteracao` quando o endpoint expõe.
`raw_data` guarda payload JSON completo pra auditoria/IA.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


# Entidades sincronizadas. Ordem importa: precisa criar antes que sync_service
# use (não há FK entre staging e core; ok criar tudo).
_STG_ENTITIES = [
    "pessoas",
    "produtos",
    "servicos",
    "vendedores",
    "contas_receber",
    "contas_pagar",
]


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
