"""
Modelos de staging Conta Azul — record-level com idempotência por
(tenant_id, external_id), espelhando o padrão Clinicorp (staging.py).

Schema uniforme:
- external_id: UUID retornado pelo Conta Azul, VARCHAR(64) por consistência com Clinicorp
- external_updated_at: `data_alteracao` quando o endpoint expõe (pessoas, eventos financeiros)
- raw_data: payload completo do JSON da API (audit trail + insumo pra IA)
- sync_job_id: rastreia qual execução trouxe o registro
- UNIQUE(tenant_id, external_id) garante upsert idempotente

São 8 tabelas: pessoas, produtos, servicos, vendedores, contas_receber,
contas_pagar, categorias, centros_custo.
"""
from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import JSON, CHAR
from app.db.base import Base


def _staging_columns():
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("external_id", String(64), nullable=False),
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
