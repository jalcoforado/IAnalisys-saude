"""Conta Azul — DRE estruturada (Fase 2 Show no Financeiro)

Cria 1 staging + 2 core pra cobrir o pacote "DRE":

  - stg_ca_categorias_dre        → /v1/financeiro/categorias-dre (árvore raw)
  - core_ca_categorias_dre       → 1 linha por nó (raiz + subitens achatados),
                                   com parent_external_id e nivel.
  - core_ca_dre_links            → ponte N:N entre nó DRE folha e
                                   `core_ca_categorias` (categoria_financeira plana
                                   que já temos sincronizada).

Decisões registradas em `docs/11_CONTAAZUL_ENDPOINTS_CATALOG.md`:
- 16 raízes hierárquicas em Parente (ex: "Receitas Operacionais", "Despesas Op.")
- Cada nó tem `subitens[]` (recursivo) + `categorias_financeiras[]` na folha
- Achatamos no CORE pra simplificar consultas top-down e bottom-up
- O staging guarda só as 16 raízes (raw_data com subárvore inteira)

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── stg_ca_categorias_dre ───────────────────────────────────
    # 1 linha POR RAIZ (16 em Parente). raw_data guarda a subárvore
    # inteira; promo recursiva achata em core_ca_categorias_dre.
    op.create_table(
        "stg_ca_categorias_dre",
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
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_stg_ca_categorias_dre_external"),
    )
    op.create_index(
        "ix_stg_ca_categorias_dre_updated",
        "stg_ca_categorias_dre",
        ["tenant_id", "external_updated_at"],
    )

    # ── core_ca_categorias_dre ──────────────────────────────────
    # 1 linha por nó (raiz + subitens achatados). Pai/filho via
    # parent_external_id (FK lógica). nivel = profundidade (0=raiz).
    op.create_table(
        "core_ca_categorias_dre",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("descricao", sa.String(255), nullable=True),
        sa.Column("codigo", sa.String(50), nullable=True),
        sa.Column("posicao", sa.Integer(), nullable=True),
        sa.Column("nivel", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("parent_external_id", sa.String(64), nullable=True),
        sa.Column("root_external_id", sa.String(64), nullable=True),  # raiz da árvore
        sa.Column("indica_totalizador", sa.Boolean(), nullable=True),
        sa.Column("representa_soma_custo_medio", sa.Boolean(), nullable=True),
        sa.Column("qtd_categorias_financeiras", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_ca_categorias_dre_external"),
    )
    op.create_index("ix_core_ca_dre_parent", "core_ca_categorias_dre",
                    ["tenant_id", "parent_external_id"])
    op.create_index("ix_core_ca_dre_root", "core_ca_categorias_dre",
                    ["tenant_id", "root_external_id"])

    # ── core_ca_dre_links ───────────────────────────────────────
    # N:N entre nó DRE folha e categoria_financeira plana
    # (core_ca_categorias.external_id). Re-populado por entidade DRE
    # a cada promo (delete by tenant_id, depois insert massa).
    op.create_table(
        "core_ca_dre_links",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("dre_external_id", sa.String(64), nullable=False),
        sa.Column("categoria_external_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dre_external_id", "categoria_external_id",
                            name="uk_core_ca_dre_links"),
    )
    op.create_index("ix_core_ca_dre_links_dre", "core_ca_dre_links",
                    ["tenant_id", "dre_external_id"])
    op.create_index("ix_core_ca_dre_links_categoria", "core_ca_dre_links",
                    ["tenant_id", "categoria_external_id"])


def downgrade() -> None:
    op.drop_table("core_ca_dre_links")
    op.drop_table("core_ca_categorias_dre")
    op.drop_table("stg_ca_categorias_dre")
