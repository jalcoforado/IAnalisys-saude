"""Conta Azul — baixas (detalhamento por parcela, Onda 2)

Cria 1 staging + 1 core pra capturar dados que NÃO vêm no `/buscar`:

  - stg_ca_parcelas_detalhe   → raw_data de /parcelas/{id} (1 chamada por parcela)
  - core_ca_baixas            → 1 linha POR BAIXA (parcela paga em N parcelas
                                pode ter N baixas; pagamento parcial = N>1)

Campos novos disponíveis (ausentes em /buscar):
  - metodo_pagamento (PIX_PAGAMENTO_INSTANTANEO, BOLETO, CARTAO_CREDITO, ...)
  - baixas[].data_pagamento (data REAL do pagamento, não só vencimento)
  - conta_financeira (em qual banco caiu)
  - conciliado (true/false — reconciliado com extrato bancário CA)
  - evento.referencia.origem (LANCAMENTO_FINANCEIRO vs VENDA)

Custo: 1 chamada por parcela paga. Parente: ~5500 parcelas pagas históricas →
sync com semaphore=3 + retry 429 leva ~30-45min na 1ª carga. Idempotente.

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── stg_ca_parcelas_detalhe ──────────────────────────────────
    # external_id = id da PARCELA (mesma chave usada em
    # core_ca_eventos_financeiros). raw_data guarda o payload inteiro
    # de /v1/financeiro/eventos-financeiros/parcelas/{id}.
    op.create_table(
        "stg_ca_parcelas_detalhe",
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
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_stg_ca_parcelas_detalhe_external"),
    )
    op.create_index(
        "ix_stg_ca_parcelas_detalhe_synced",
        "stg_ca_parcelas_detalhe",
        ["tenant_id", "synced_at"],
    )

    # ── core_ca_baixas ───────────────────────────────────────────
    # 1 linha POR BAIXA (pagamento efetivo). Uma parcela pode ter múltiplas
    # baixas se foi paga parcialmente. external_id = id da baixa (não da
    # parcela). parcela_external_id linka com core_ca_eventos_financeiros.
    op.create_table(
        "core_ca_baixas",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),  # id da baixa
        sa.Column("parcela_external_id", sa.String(64), nullable=False),
        sa.Column("evento_external_id", sa.String(64), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        # Tipo + datas
        sa.Column("tipo", sa.String(20), nullable=True),  # RECEITA | DESPESA
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("data_vencimento", sa.Date(), nullable=True),
        sa.Column("data_competencia", sa.Date(), nullable=True),
        # Forma de pagamento
        sa.Column("metodo_pagamento", sa.String(60), nullable=True),
        # Valores (composição)
        sa.Column("valor_pago", sa.Numeric(15, 2), nullable=True),
        sa.Column("valor_bruto", sa.Numeric(15, 2), nullable=True),
        sa.Column("valor_liquido", sa.Numeric(15, 2), nullable=True),
        sa.Column("multa", sa.Numeric(15, 2), nullable=True),
        sa.Column("juros", sa.Numeric(15, 2), nullable=True),
        sa.Column("desconto", sa.Numeric(15, 2), nullable=True),
        sa.Column("taxa", sa.Numeric(15, 2), nullable=True),
        # Conta destino (em qual banco caiu)
        sa.Column("conta_financeira_external_id", sa.String(64), nullable=True),
        sa.Column("conta_financeira_nome", sa.String(255), nullable=True),
        sa.Column("conta_financeira_banco", sa.String(60), nullable=True),
        # Conciliação
        sa.Column("conciliado", sa.Boolean(), nullable=True),
        sa.Column("baixa_agendada", sa.Boolean(), nullable=True),
        # Origem (VENDA vs LANCAMENTO_FINANCEIRO)
        sa.Column("origem_referencia", sa.String(40), nullable=True),
        # NSU pra cartões
        sa.Column("nsu", sa.String(60), nullable=True),
        # Pessoa associada (snapshot)
        sa.Column("pessoa_external_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_ca_baixas_external"),
    )
    op.create_index(
        "ix_core_ca_baixas_tipo_data_pagamento", "core_ca_baixas",
        ["tenant_id", "tipo", "data_pagamento"],
    )
    op.create_index(
        "ix_core_ca_baixas_metodo_data", "core_ca_baixas",
        ["tenant_id", "metodo_pagamento", "data_pagamento"],
    )
    op.create_index(
        "ix_core_ca_baixas_parcela", "core_ca_baixas",
        ["tenant_id", "parcela_external_id"],
    )
    op.create_index(
        "ix_core_ca_baixas_conta", "core_ca_baixas",
        ["tenant_id", "conta_financeira_external_id"],
    )


def downgrade() -> None:
    op.drop_table("core_ca_baixas")
    op.drop_table("stg_ca_parcelas_detalhe")
