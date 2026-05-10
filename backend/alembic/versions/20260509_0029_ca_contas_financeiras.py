"""Conta Azul — saldos bancários (Fase 1 Show no Financeiro)

Cria 3 staging + 1 core pra cobrir o pacote de "Saldo Bancário":

  - stg_ca_contas_financeiras   → /v1/conta-financeira (lista de contas)
  - stg_ca_saldos_atuais        → /v1/conta-financeira/{id}/saldo-atual (snapshot por conta)
  - stg_ca_saldos_iniciais      → /v1/financeiro/eventos-financeiros/saldo-inicial
                                  (linhas por conta × tipo × data_competencia)
  - core_ca_contas_financeiras  → 1 linha por conta com banco/agência/saldo atual

Pegadinhas confirmadas em 2026-05-09:
  - /saldo-atual retorna `{"saldo_atual": <number>}` (sem wrapper de lista)
    e pode ser negativo (aplicação BB Parente = -9,59).
  - /saldo-inicial: datetime ISO **SEM Z** — `2026-04-01T00:00:00`.
  - Wrapper `{"itens_totais", "itens": [...]}` em PT (não `items`).

Saldos iniciais não têm `id` natural — usamos external_id artificial
`{conta_id}|{tipo}|{data_competencia_iso}` pra preservar idempotência.
Saldos atuais usam `external_id = conta_id` (snapshot único por conta).

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


_STG_ENTITIES = ("contas_financeiras", "saldos_atuais", "saldos_iniciais")


def upgrade() -> None:
    for entity in _STG_ENTITIES:
        table_name = f"stg_ca_{entity}"
        op.create_table(
            table_name,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
            sa.Column("external_id", sa.String(160), nullable=False),
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

    op.create_table(
        "core_ca_contas_financeiras",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("banco", sa.String(255), nullable=True),
        sa.Column("codigo_banco", sa.String(20), nullable=True),
        sa.Column("agencia", sa.String(50), nullable=True),
        sa.Column("numero", sa.String(50), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=True),  # CORRENTE | APLICACAO | ...
        sa.Column("ativo", sa.Boolean(), nullable=True),
        sa.Column("conta_padrao", sa.Boolean(), nullable=True),
        sa.Column("possui_config_boleto", sa.Boolean(), nullable=True),
        sa.Column("saldo_atual", sa.Numeric(15, 2), nullable=True),
        sa.Column("saldo_atualizado_em", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_ca_contas_financeiras_external"),
    )
    op.create_index(
        "ix_core_ca_contas_financeiras_ativo",
        "core_ca_contas_financeiras",
        ["tenant_id", "ativo"],
    )


def downgrade() -> None:
    op.drop_table("core_ca_contas_financeiras")
    for entity in reversed(_STG_ENTITIES):
        op.drop_table(f"stg_ca_{entity}")
