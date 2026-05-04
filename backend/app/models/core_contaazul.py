"""
Modelos CORE Conta Azul — camada relacional limpa derivada do staging.

8 tabelas:
- 6 cadastros (1:1 com staging): pessoas, categorias, centros_custo,
  produtos, servicos, vendedores
- 1 fato granular: eventos_financeiros (1 linha POR PARCELA, unifica
  contas a receber + a pagar com `tipo` discriminator)
- 1 detalhe: rateio (N linhas por parcela, 1 por par categoria×CC)

Decisões registradas em docs/11_CONTAAZUL_ENDPOINTS_CATALOG.md e na
migration 0018.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


def _common_cols():
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("external_id", String(64), nullable=False),
        Column("is_deleted", Boolean, nullable=False, default=False),
        Column("external_updated_at", DateTime, nullable=True),
        Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
        Column("updated_at", DateTime, nullable=False,
               server_default=func.current_timestamp(), onupdate=func.current_timestamp()),
    ]


def _common_args(table_name: str):
    return (UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),)


class CoreCaPessoas(Base):
    __tablename__ = "core_ca_pessoas"
    __table_args__ = (
        *_common_args(__tablename__),
        Index("ix_core_ca_pessoas_documento", "tenant_id", "documento"),
    )
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    documento = Column(String(32), nullable=True)
    nome = Column(String(500), nullable=True)
    tipo_pessoa = Column(String(20), nullable=True)
    is_cliente = Column(Boolean, nullable=False, default=False)
    is_fornecedor = Column(Boolean, nullable=False, default=False)
    is_transportadora = Column(Boolean, nullable=False, default=False)
    email = Column(String(255), nullable=True)
    telefone = Column(String(50), nullable=True)
    ativo = Column(Boolean, nullable=True)
    id_legado = Column(BigInteger, nullable=True)
    uuid_legado = Column(String(64), nullable=True)


class CoreCaCategorias(Base):
    __tablename__ = "core_ca_categorias"
    __table_args__ = _common_args(__tablename__)
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    nome = Column(String(255), nullable=True)
    tipo = Column(String(20), nullable=True)  # RECEITA / DESPESA
    categoria_pai_external_id = Column(String(64), nullable=True)
    entrada_dre = Column(String(100), nullable=True)
    considera_custo_dre = Column(Boolean, nullable=True)
    versao = Column(Integer, nullable=True)


class CoreCaCentrosCusto(Base):
    __tablename__ = "core_ca_centros_custo"
    __table_args__ = _common_args(__tablename__)
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    codigo = Column(String(50), nullable=True)
    nome = Column(String(255), nullable=True)
    ativo = Column(Boolean, nullable=True)


class CoreCaProdutos(Base):
    __tablename__ = "core_ca_produtos"
    __table_args__ = _common_args(__tablename__)
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    codigo = Column(String(50), nullable=True)
    nome = Column(String(500), nullable=True)
    tipo = Column(String(20), nullable=True)  # PRODUCT / SERVICE
    status = Column(String(20), nullable=True)
    valor_venda = Column(Numeric(15, 4), nullable=True)
    custo_medio = Column(Numeric(15, 4), nullable=True)
    saldo = Column(Numeric(15, 4), nullable=True)
    ean = Column(String(50), nullable=True)


class CoreCaServicos(Base):
    __tablename__ = "core_ca_servicos"
    __table_args__ = _common_args(__tablename__)
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    codigo = Column(String(50), nullable=True)
    nome = Column(String(500), nullable=True)
    descricao = Column(Text, nullable=True)
    preco = Column(Numeric(15, 4), nullable=True)
    custo = Column(Numeric(15, 4), nullable=True)
    status = Column(String(20), nullable=True)
    tipo_servico = Column(String(20), nullable=True)


class CoreCaVendedores(Base):
    __tablename__ = "core_ca_vendedores"
    __table_args__ = _common_args(__tablename__)
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    nome = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)


class CoreCaEventosFinanceiros(Base):
    __tablename__ = "core_ca_eventos_financeiros"
    __table_args__ = (
        *_common_args(__tablename__),
        Index("ix_core_ca_eventos_tipo_data", "tenant_id", "tipo", "data_vencimento"),
        Index("ix_core_ca_eventos_pessoa", "tenant_id", "pessoa_external_id"),
    )
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    tipo = Column(String(20), nullable=False)  # RECEITA / DESPESA
    descricao = Column(Text, nullable=True)
    status = Column(String(30), nullable=True)  # EN
    status_pt = Column(String(30), nullable=True)
    pessoa_external_id = Column(String(64), nullable=True)
    pessoa_nome = Column(String(500), nullable=True)
    valor_total = Column(Numeric(15, 2), nullable=True)
    valor_pago = Column(Numeric(15, 2), nullable=True)
    valor_em_aberto = Column(Numeric(15, 2), nullable=True)
    data_vencimento = Column(Date, nullable=True)
    data_competencia = Column(Date, nullable=True)
    data_criacao = Column(DateTime, nullable=True)
    evento_origem_id = Column(String(64), nullable=True)
    tem_rateio_multiplo = Column(Boolean, nullable=False, default=False)
    qtd_categorias = Column(Integer, nullable=False, default=0)
    qtd_centros_custo = Column(Integer, nullable=False, default=0)


class CoreCaRateio(Base):
    __tablename__ = "core_ca_rateio"
    __table_args__ = (
        Index("ix_core_ca_rateio_evento", "tenant_id", "evento_financeiro_external_id"),
        Index("ix_core_ca_rateio_categoria", "tenant_id", "categoria_external_id"),
        Index("ix_core_ca_rateio_centro_custo", "tenant_id", "centro_custo_external_id"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    evento_financeiro_external_id = Column(String(64), nullable=False)
    categoria_external_id = Column(String(64), nullable=True)
    centro_custo_external_id = Column(String(64), nullable=True)
    valor = Column(Numeric(15, 2), nullable=False, default=0)
    is_aproximado = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())
