"""core layer Conta Azul

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-04

Cria 8 tabelas core_ca_*:
- 6 cadastros (1:1 com staging): pessoas, categorias, centros_custo,
  produtos, servicos, vendedores
- 1 fato granular: eventos_financeiros (1 linha POR PARCELA, unifica
  receber+pagar com `tipo` discriminator RECEITA/DESPESA)
- 1 detalhe de rateio: core_ca_rateio (N linhas por parcela, 1 por par
  categoria×centro_custo)

Convenções (mesmo padrão do core CC, migration 0006):
- PK: id BIGINT autoincrement
- Idempotência: UNIQUE(tenant_id, external_id)
- Sem FK rígida entre core_* (integridade lógica via external_id)
- Soft delete: is_deleted BOOLEAN
- Timestamps locais (created_at, updated_at)
- Timestamp da origem: external_updated_at quando o endpoint expõe

Decisões específicas pro CA (registradas em docs/11_CONTAAZUL_ENDPOINTS_CATALOG.md):
- Pessoas têm perfis múltiplos (cliente+fornecedor+transportadora) — 3
  booleans em vez de tipo único + perfis_raw guarda original
- Status: usa o `status` em EN (ACQUITTED/OVERDUE/PENDING/PARTIAL) — bug
  do CA faz `status_traduzido` retornar "RECEBIDO" em conta a pagar
- Rateio: 1cat+1cc é exato (~80%); rateio múltiplo (~20%) usa produto
  cartesiano com valor dividido proporcionalmente + flag is_aproximado
- Endpoint /buscar achata o rateio detalhado — pra fidelidade total
  precisaria buscar /parcelas/{id} (1.660 chamadas extras), fica como
  PR futuro sob demanda
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def _common_columns():
    """Colunas comuns a toda core_ca_* (espelha core_* do CC)."""
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
    ]


def _common_constraints(table_name: str):
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
    ]


def upgrade() -> None:
    # ── core_ca_pessoas ──────────────────────────────────────────
    # Cliente + fornecedor + transportadora unificados. Booleans em vez de
    # tipo único porque pessoa pode ter múltiplos perfis (10 da Parente são
    # cliente E fornecedor). `documento` é UNIQUE por tenant pra cross-link
    # com core_patients (CC) via CPF/CNPJ.
    op.create_table(
        "core_ca_pessoas",
        *_common_columns(),
        sa.Column("documento", sa.String(32), nullable=True),
        sa.Column("nome", sa.String(500), nullable=True),
        sa.Column("tipo_pessoa", sa.String(20), nullable=True),  # Física/Jurídica/Estrangeira
        sa.Column("is_cliente", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_fornecedor", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_transportadora", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telefone", sa.String(50), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=True),
        sa.Column("id_legado", sa.BigInteger(), nullable=True),
        sa.Column("uuid_legado", sa.String(64), nullable=True),
        *_common_constraints("core_ca_pessoas"),
    )
    op.create_index("ix_core_ca_pessoas_documento", "core_ca_pessoas", ["tenant_id", "documento"])

    # ── core_ca_categorias ───────────────────────────────────────
    # Hierarquia pai/filho via `categoria_pai_external_id` (FK lógica, sem FK
    # rígida — ver decisão em ROADMAP). entrada_dre permite agrupamento DRE.
    op.create_table(
        "core_ca_categorias",
        *_common_columns(),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=True),  # RECEITA / DESPESA
        sa.Column("categoria_pai_external_id", sa.String(64), nullable=True),
        sa.Column("entrada_dre", sa.String(100), nullable=True),
        sa.Column("considera_custo_dre", sa.Boolean(), nullable=True),
        sa.Column("versao", sa.Integer(), nullable=True),
        *_common_constraints("core_ca_categorias"),
    )

    # ── core_ca_centros_custo ────────────────────────────────────
    op.create_table(
        "core_ca_centros_custo",
        *_common_columns(),
        sa.Column("codigo", sa.String(50), nullable=True),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=True),
        *_common_constraints("core_ca_centros_custo"),
    )

    # ── core_ca_produtos ─────────────────────────────────────────
    op.create_table(
        "core_ca_produtos",
        *_common_columns(),
        sa.Column("codigo", sa.String(50), nullable=True),
        sa.Column("nome", sa.String(500), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=True),  # PRODUCT / SERVICE
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("valor_venda", sa.Numeric(15, 4), nullable=True),
        sa.Column("custo_medio", sa.Numeric(15, 4), nullable=True),
        sa.Column("saldo", sa.Numeric(15, 4), nullable=True),
        sa.Column("ean", sa.String(50), nullable=True),
        *_common_constraints("core_ca_produtos"),
    )

    # ── core_ca_servicos ─────────────────────────────────────────
    op.create_table(
        "core_ca_servicos",
        *_common_columns(),
        sa.Column("codigo", sa.String(50), nullable=True),
        sa.Column("nome", sa.String(500), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("preco", sa.Numeric(15, 4), nullable=True),
        sa.Column("custo", sa.Numeric(15, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("tipo_servico", sa.String(20), nullable=True),  # PRESTADO / CONTRATADO
        *_common_constraints("core_ca_servicos"),
    )

    # ── core_ca_vendedores ───────────────────────────────────────
    op.create_table(
        "core_ca_vendedores",
        *_common_columns(),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        *_common_constraints("core_ca_vendedores"),
    )

    # ── core_ca_eventos_financeiros ──────────────────────────────
    # 1 linha POR PARCELA. Unifica contas a receber + a pagar com `tipo`
    # discriminator. external_id = id da PARCELA (não do evento).
    # `evento_origem_id` é o UUID do EVENTO (referência futura para link
    # com /v1/venda/{id} via referencia.origem='VENDA').
    op.create_table(
        "core_ca_eventos_financeiros",
        *_common_columns(),
        sa.Column("tipo", sa.String(20), nullable=False),  # RECEITA / DESPESA
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=True),  # ACQUITTED/OVERDUE/PENDING/PARTIAL (EN)
        sa.Column("status_pt", sa.String(30), nullable=True),  # nossa tradução (status_traduzido do CA tem bug)
        sa.Column("pessoa_external_id", sa.String(64), nullable=True),
        sa.Column("pessoa_nome", sa.String(500), nullable=True),  # snapshot pra órfãos
        sa.Column("valor_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("valor_pago", sa.Numeric(15, 2), nullable=True),
        sa.Column("valor_em_aberto", sa.Numeric(15, 2), nullable=True),
        sa.Column("data_vencimento", sa.Date(), nullable=True),
        sa.Column("data_competencia", sa.Date(), nullable=True),
        sa.Column("data_criacao", sa.DateTime(), nullable=True),
        sa.Column("evento_origem_id", sa.String(64), nullable=True),  # UUID do evento (não da parcela)
        sa.Column("tem_rateio_multiplo", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("qtd_categorias", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("qtd_centros_custo", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_common_constraints("core_ca_eventos_financeiros"),
    )
    op.create_index("ix_core_ca_eventos_tipo_data", "core_ca_eventos_financeiros",
                    ["tenant_id", "tipo", "data_vencimento"])
    op.create_index("ix_core_ca_eventos_pessoa", "core_ca_eventos_financeiros",
                    ["tenant_id", "pessoa_external_id"])

    # ── core_ca_rateio ───────────────────────────────────────────
    # N linhas por parcela. evento_financeiro_external_id = external_id da
    # parcela em core_ca_eventos_financeiros. is_aproximado=true quando o
    # valor foi dividido proporcionalmente por falta do detalhe (rateio múltiplo).
    op.create_table(
        "core_ca_rateio",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("evento_financeiro_external_id", sa.String(64), nullable=False),
        sa.Column("categoria_external_id", sa.String(64), nullable=True),
        sa.Column("centro_custo_external_id", sa.String(64), nullable=True),
        sa.Column("valor", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_aproximado", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Índice composto: rateio é apagado/repopulado por evento (não tem upsert
    # natural por external_id porque pode ter múltiplas linhas por evento).
    op.create_index("ix_core_ca_rateio_evento", "core_ca_rateio",
                    ["tenant_id", "evento_financeiro_external_id"])
    op.create_index("ix_core_ca_rateio_categoria", "core_ca_rateio",
                    ["tenant_id", "categoria_external_id"])
    op.create_index("ix_core_ca_rateio_centro_custo", "core_ca_rateio",
                    ["tenant_id", "centro_custo_external_id"])


def downgrade() -> None:
    op.drop_table("core_ca_rateio")
    op.drop_table("core_ca_eventos_financeiros")
    op.drop_table("core_ca_vendedores")
    op.drop_table("core_ca_servicos")
    op.drop_table("core_ca_produtos")
    op.drop_table("core_ca_centros_custo")
    op.drop_table("core_ca_categorias")
    op.drop_table("core_ca_pessoas")
