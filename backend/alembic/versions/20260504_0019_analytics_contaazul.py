"""analytics layer Conta Azul

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-04

Cria 4 tabelas pra completar o star schema CA:
- dim_pessoa_ca       (clientes + fornecedores + transportadoras)
- dim_categoria_ca    (com hierarquia pai/filho via external_id)
- dim_centro_custo_ca (5 unidades do grupo Parente)
- fato_caixa          (1 linha POR LINHA DE RATEIO de core_ca_rateio)

Reusa `dim_tempo` existente — vencimento da parcela vira date_key.

`fato_caixa` é granular no rateio (não na parcela): permite agregar por
categoria/CC sem perder precisão. 14k linhas vs 8k parcelas.
- valor_rateado: valor da linha de rateio (já dividido pela transform)
- valor_pago_rateado: parcela.valor_pago × (valor_rateado / valor_total)
- valor_em_aberto_rateado: idem com valor_em_aberto

Idempotência:
- dim_*_ca: INSERT ... ON DUPLICATE KEY UPDATE por external_id
- fato_caixa: DELETE + INSERT do tenant (consistente com core_ca_rateio
  que também é DELETE + INSERT — não há chave natural única na linha
  de rateio).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def _common_dim_cols():
    """Colunas comuns às dim_*_ca."""
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def _common_dim_args(table_name: str):
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
    ]


def upgrade() -> None:
    # ── dim_pessoa_ca ────────────────────────────────────────────
    op.create_table(
        "dim_pessoa_ca",
        *_common_dim_cols(),
        sa.Column("documento", sa.String(32), nullable=True),
        sa.Column("nome", sa.String(500), nullable=True),
        sa.Column("tipo_pessoa", sa.String(20), nullable=True),
        sa.Column("is_cliente", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_fornecedor", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_transportadora", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("ativo", sa.Boolean(), nullable=True),
        *_common_dim_args("dim_pessoa_ca"),
    )
    op.create_index("ix_dim_pessoa_ca_documento", "dim_pessoa_ca", ["tenant_id", "documento"])

    # ── dim_categoria_ca ─────────────────────────────────────────
    op.create_table(
        "dim_categoria_ca",
        *_common_dim_cols(),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=True),
        sa.Column("categoria_pai_external_id", sa.String(64), nullable=True),
        sa.Column("entrada_dre", sa.String(100), nullable=True),
        sa.Column("considera_custo_dre", sa.Boolean(), nullable=True),
        *_common_dim_args("dim_categoria_ca"),
    )
    op.create_index("ix_dim_categoria_ca_tipo", "dim_categoria_ca", ["tenant_id", "tipo"])
    op.create_index("ix_dim_categoria_ca_dre", "dim_categoria_ca", ["tenant_id", "entrada_dre"])

    # ── dim_centro_custo_ca ──────────────────────────────────────
    op.create_table(
        "dim_centro_custo_ca",
        *_common_dim_cols(),
        sa.Column("codigo", sa.String(50), nullable=True),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=True),
        *_common_dim_args("dim_centro_custo_ca"),
    )

    # ── fato_caixa ───────────────────────────────────────────────
    # Granularidade: linha de rateio (não parcela). 1 parcela com 2 cats e 3
    # CCs gera até 6 linhas no fato (produto cartesiano). Permite GROUP BY
    # categoria/CC sem dupla contagem nem perda.
    # date_key = data_vencimento (sempre presente).
    op.create_table(
        "fato_caixa",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("parcela_external_id", sa.String(64), nullable=False),
        sa.Column("evento_origem_id", sa.String(64), nullable=True),
        # Chaves dimensionais (FK lógica via external_id)
        sa.Column("pessoa_external_id", sa.String(64), nullable=True),
        sa.Column("categoria_external_id", sa.String(64), nullable=True),
        sa.Column("centro_custo_external_id", sa.String(64), nullable=True),
        # dim_tempo (data_vencimento)
        sa.Column("date_key", sa.Date(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year_month_key", sa.String(7), nullable=False),
        # data_competencia (segunda data útil pra DRE — nullable)
        sa.Column("date_key_competencia", sa.Date(), nullable=True),
        sa.Column("year_competencia", sa.Integer(), nullable=True),
        sa.Column("month_competencia", sa.Integer(), nullable=True),
        sa.Column("year_month_competencia_key", sa.String(7), nullable=True),
        # Atributos discriminantes
        sa.Column("tipo", sa.String(20), nullable=False),  # RECEITA / DESPESA
        sa.Column("status", sa.String(30), nullable=True),  # ACQUITTED/OVERDUE/PENDING/PARTIAL
        sa.Column("is_pago", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_vencido", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_em_aberto", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_aproximado", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        # Métricas (já rateadas pela proporção do rateio)
        sa.Column("valor_rateado", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("valor_pago_rateado", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("valor_em_aberto_rateado", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("dias_atraso", sa.Integer(), nullable=True),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Índices de filtro/agregação típicos do dashboard financeiro
    op.create_index("ix_fato_caixa_date", "fato_caixa", ["tenant_id", "date_key"])
    op.create_index("ix_fato_caixa_year_month", "fato_caixa", ["tenant_id", "year_month_key"])
    op.create_index("ix_fato_caixa_tipo_ym", "fato_caixa", ["tenant_id", "tipo", "year_month_key"])
    op.create_index("ix_fato_caixa_categoria", "fato_caixa", ["tenant_id", "categoria_external_id"])
    op.create_index("ix_fato_caixa_centro_custo", "fato_caixa", ["tenant_id", "centro_custo_external_id"])
    op.create_index("ix_fato_caixa_pessoa", "fato_caixa", ["tenant_id", "pessoa_external_id"])
    op.create_index("ix_fato_caixa_parcela", "fato_caixa", ["tenant_id", "parcela_external_id"])


def downgrade() -> None:
    op.drop_table("fato_caixa")
    op.drop_table("dim_centro_custo_ca")
    op.drop_table("dim_categoria_ca")
    op.drop_table("dim_pessoa_ca")
