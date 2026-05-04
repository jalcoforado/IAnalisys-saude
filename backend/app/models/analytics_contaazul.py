"""
Modelos ANALYTICS Conta Azul — star schema derivado do CORE.

3 dimensões + 1 fato:
- DimPessoaCa
- DimCategoriaCa
- DimCentroCustoCa
- FatoCaixa (granular no rateio: 1 linha por par categoria×CC dentro de cada parcela)

Reusa `dim_tempo` existente (do CC) — o calendário é universal.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


def _common_dim_cols():
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("external_id", String(64), nullable=False),
        Column("rebuilt_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    ]


class DimPessoaCa(Base):
    __tablename__ = "dim_pessoa_ca"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_pessoa_ca_external"),
        Index("ix_dim_pessoa_ca_documento", "tenant_id", "documento"),
    )
    id, tenant_id, external_id, rebuilt_at = _common_dim_cols()
    documento = Column(String(32), nullable=True)
    nome = Column(String(500), nullable=True)
    tipo_pessoa = Column(String(20), nullable=True)
    is_cliente = Column(Boolean, nullable=False, default=False)
    is_fornecedor = Column(Boolean, nullable=False, default=False)
    is_transportadora = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=True)


class DimCategoriaCa(Base):
    __tablename__ = "dim_categoria_ca"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_categoria_ca_external"),
        Index("ix_dim_categoria_ca_tipo", "tenant_id", "tipo"),
        Index("ix_dim_categoria_ca_dre", "tenant_id", "entrada_dre"),
    )
    id, tenant_id, external_id, rebuilt_at = _common_dim_cols()
    nome = Column(String(255), nullable=True)
    tipo = Column(String(20), nullable=True)  # RECEITA / DESPESA
    categoria_pai_external_id = Column(String(64), nullable=True)
    entrada_dre = Column(String(100), nullable=True)
    considera_custo_dre = Column(Boolean, nullable=True)


class DimCentroCustoCa(Base):
    __tablename__ = "dim_centro_custo_ca"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_centro_custo_ca_external"),
    )
    id, tenant_id, external_id, rebuilt_at = _common_dim_cols()
    codigo = Column(String(50), nullable=True)
    nome = Column(String(255), nullable=True)
    ativo = Column(Boolean, nullable=True)


class FatoCaixa(Base):
    __tablename__ = "fato_caixa"
    __table_args__ = (
        Index("ix_fato_caixa_date", "tenant_id", "date_key"),
        Index("ix_fato_caixa_year_month", "tenant_id", "year_month_key"),
        Index("ix_fato_caixa_tipo_ym", "tenant_id", "tipo", "year_month_key"),
        Index("ix_fato_caixa_categoria", "tenant_id", "categoria_external_id"),
        Index("ix_fato_caixa_centro_custo", "tenant_id", "centro_custo_external_id"),
        Index("ix_fato_caixa_pessoa", "tenant_id", "pessoa_external_id"),
        Index("ix_fato_caixa_parcela", "tenant_id", "parcela_external_id"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    parcela_external_id = Column(String(64), nullable=False)
    evento_origem_id = Column(String(64), nullable=True)
    # FK lógica via external_id
    pessoa_external_id = Column(String(64), nullable=True)
    categoria_external_id = Column(String(64), nullable=True)
    centro_custo_external_id = Column(String(64), nullable=True)
    # dim_tempo (data_vencimento)
    date_key = Column(Date, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year_month_key = Column(String(7), nullable=False)
    # data_competencia
    date_key_competencia = Column(Date, nullable=True)
    year_competencia = Column(Integer, nullable=True)
    month_competencia = Column(Integer, nullable=True)
    year_month_competencia_key = Column(String(7), nullable=True)
    # Discriminantes
    tipo = Column(String(20), nullable=False)  # RECEITA / DESPESA
    status = Column(String(30), nullable=True)
    is_pago = Column(Boolean, nullable=False, default=False)
    is_vencido = Column(Boolean, nullable=False, default=False)
    is_em_aberto = Column(Boolean, nullable=False, default=False)
    is_aproximado = Column(Boolean, nullable=False, default=False)
    # Métricas rateadas
    valor_rateado = Column(Numeric(15, 2), nullable=False, default=0)
    valor_pago_rateado = Column(Numeric(15, 2), nullable=False, default=0)
    valor_em_aberto_rateado = Column(Numeric(15, 2), nullable=False, default=0)
    dias_atraso = Column(Integer, nullable=True)
    rebuilt_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
