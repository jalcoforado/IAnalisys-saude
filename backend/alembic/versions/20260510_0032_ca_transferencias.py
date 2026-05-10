"""Conta Azul — transferências entre contas (Show no Financeiro Fase 3)

Cria 1 staging + 1 core pra capturar transferências internas entre contas
financeiras (PIX entre Sicredi e Unicredi, aplicação ↔ corrente, etc.).

Importância: transferências NÃO são receita nem despesa — são movimentação
interna. Hoje elas não vazam em fato_caixa (validado no banco), mas o card
"Transferências internas" no /financeiro vai mostrar volume e top fluxos.

Endpoint origem: GET /v1/financeiro/transferencias
  - Wrapper: {itens_totais, itens: [...]}
  - Obrigatório: data_inicio + data_fim (datetime ISO)
  - Volume Parente: ~12/mês

Payload por transferência:
  - id, descricao, valor, data
  - origem: { conta_financeira: {id, nome, instituicao_bancaria},
              composicao_valor: {valor_bruto, juros, multa, valor_liquido, desconto, taxa},
              data }
  - destino: { ...mesmo formato... }

Revision ID: 0032
Revises: 0031
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── stg_ca_transferencias ────────────────────────────────────
    op.create_table(
        "stg_ca_transferencias",
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
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_stg_ca_transferencias_external"),
    )
    op.create_index(
        "ix_stg_ca_transferencias_synced",
        "stg_ca_transferencias",
        ["tenant_id", "synced_at"],
    )

    # ── core_ca_transferencias ───────────────────────────────────
    # Achatado: 1 linha por transferência. composição vem de origem (o lado
    # que "envia" o dinheiro — destino tem espelho com mesmos números na
    # prática, validado nas 12 transferências de abr/26 Parente).
    op.create_table(
        "core_ca_transferencias",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("valor", sa.Numeric(15, 2), nullable=False),
        # Origem (de onde sai)
        sa.Column("origem_conta_external_id", sa.String(64), nullable=True),
        sa.Column("origem_conta_nome", sa.String(255), nullable=True),
        sa.Column("origem_conta_banco", sa.String(60), nullable=True),
        # Destino (para onde vai)
        sa.Column("destino_conta_external_id", sa.String(64), nullable=True),
        sa.Column("destino_conta_nome", sa.String(255), nullable=True),
        sa.Column("destino_conta_banco", sa.String(60), nullable=True),
        # Composição do valor (vem da origem; tarifas/encargos)
        sa.Column("valor_bruto", sa.Numeric(15, 2), nullable=True),
        sa.Column("valor_liquido", sa.Numeric(15, 2), nullable=True),
        sa.Column("juros", sa.Numeric(15, 2), nullable=True),
        sa.Column("multa", sa.Numeric(15, 2), nullable=True),
        sa.Column("desconto", sa.Numeric(15, 2), nullable=True),
        sa.Column("taxa", sa.Numeric(15, 2), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_ca_transferencias_external"),
    )
    op.create_index(
        "ix_core_ca_transferencias_data",
        "core_ca_transferencias",
        ["tenant_id", "data"],
    )
    op.create_index(
        "ix_core_ca_transferencias_origem",
        "core_ca_transferencias",
        ["tenant_id", "origem_conta_external_id"],
    )
    op.create_index(
        "ix_core_ca_transferencias_destino",
        "core_ca_transferencias",
        ["tenant_id", "destino_conta_external_id"],
    )


def downgrade() -> None:
    op.drop_table("core_ca_transferencias")
    op.drop_table("stg_ca_transferencias")
