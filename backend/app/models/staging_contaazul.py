"""
Modelos de staging Conta Azul — record-level com idempotência por
(tenant_id, external_id), espelhando o padrão Clinicorp (staging.py).

Schema uniforme:
- external_id: UUID retornado pelo Conta Azul, VARCHAR(64) por consistência com Clinicorp
- external_updated_at: `data_alteracao` quando o endpoint expõe (pessoas, eventos financeiros)
- raw_data: payload completo do JSON da API (audit trail + insumo pra IA)
- sync_job_id: rastreia qual execução trouxe o registro
- UNIQUE(tenant_id, external_id) garante upsert idempotente

São 11 tabelas: pessoas, produtos, servicos, vendedores, contas_receber,
contas_pagar, categorias, centros_custo, contas_financeiras, saldos_atuais,
saldos_iniciais.

As 3 últimas (Fase 1 "Show no Financeiro") usam external_id mais largo
(VARCHAR 160) porque saldos_iniciais usa chave composta artificial
`{conta_id}|{tipo}|{data_competencia}` — UUID natural não existe.
"""
from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import JSON, CHAR
from app.db.base import Base


def _staging_columns(external_id_len: int = 64):
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("external_id", String(external_id_len), nullable=False),
        Column("external_updated_at", DateTime, nullable=True),
        Column("raw_data", JSON, nullable=False),
        Column("synced_at", DateTime, nullable=False, server_default=func.current_timestamp()),
        Column("sync_job_id", BigInteger, ForeignKey("sync_jobs.id"), nullable=True),
    ]


def _staging_table_args(table_name: str):
    return (
        UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
        Index(f"ix_{table_name}_updated", "tenant_id", "external_updated_at"),
    )


class StgCaPessoas(Base):
    __tablename__ = "stg_ca_pessoas"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaProdutos(Base):
    __tablename__ = "stg_ca_produtos"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaServicos(Base):
    __tablename__ = "stg_ca_servicos"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaVendedores(Base):
    __tablename__ = "stg_ca_vendedores"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaContasReceber(Base):
    __tablename__ = "stg_ca_contas_receber"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaContasPagar(Base):
    __tablename__ = "stg_ca_contas_pagar"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaCategorias(Base):
    __tablename__ = "stg_ca_categorias"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaCentrosCusto(Base):
    __tablename__ = "stg_ca_centros_custo"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaContasFinanceiras(Base):
    __tablename__ = "stg_ca_contas_financeiras"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns(160)


class StgCaSaldosAtuais(Base):
    """Snapshot do saldo atual por conta — external_id = id da conta."""
    __tablename__ = "stg_ca_saldos_atuais"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns(160)


class StgCaSaldosIniciais(Base):
    """Saldo inicial por conta×tipo×data_competencia.

    external_id artificial = `{conta_id}|{tipo}|{data_competencia_iso}` —
    o payload da API não traz id natural.
    """
    __tablename__ = "stg_ca_saldos_iniciais"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns(160)


class StgCaCategoriasDre(Base):
    """Árvore DRE — 1 linha por raiz, raw_data guarda a subárvore inteira."""
    __tablename__ = "stg_ca_categorias_dre"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaParcelasDetalhe(Base):
    """Detalhe completo de UMA parcela paga via /parcelas/{id}.

    Pega campos ausentes em /buscar: metodo_pagamento, baixas[].data_pagamento,
    conta_financeira destino, conciliado, evento.referencia.origem.

    external_id = id da parcela (mesma chave de core_ca_eventos_financeiros).
    """
    __tablename__ = "stg_ca_parcelas_detalhe"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCaTransferencias(Base):
    """Transferências entre contas financeiras (Fase 3 Show no Financeiro).

    Movimentação interna — não é receita nem despesa. external_id = id da
    transferência. raw_data tem origem/destino com composicao_valor.
    """
    __tablename__ = "stg_ca_transferencias"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()
