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


class CoreCaCategoriasDre(Base):
    """Árvore DRE achatada. parent_external_id = pai (NULL nas raízes)."""
    __tablename__ = "core_ca_categorias_dre"
    __table_args__ = (
        *_common_args(__tablename__),
        Index("ix_core_ca_dre_parent", "tenant_id", "parent_external_id"),
        Index("ix_core_ca_dre_root", "tenant_id", "root_external_id"),
    )
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    descricao = Column(String(255), nullable=True)
    codigo = Column(String(50), nullable=True)
    posicao = Column(Integer, nullable=True)
    nivel = Column(Integer, nullable=False, default=0)
    parent_external_id = Column(String(64), nullable=True)
    root_external_id = Column(String(64), nullable=True)
    indica_totalizador = Column(Boolean, nullable=True)
    representa_soma_custo_medio = Column(Boolean, nullable=True)
    qtd_categorias_financeiras = Column(Integer, nullable=False, default=0)


class CoreCaDreLinks(Base):
    """Ponte N:N entre nó DRE e categoria_financeira plana."""
    __tablename__ = "core_ca_dre_links"
    __table_args__ = (
        Index("ix_core_ca_dre_links_dre", "tenant_id", "dre_external_id"),
        Index("ix_core_ca_dre_links_categoria", "tenant_id", "categoria_external_id"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    dre_external_id = Column(String(64), nullable=False)
    categoria_external_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


class CoreCaBaixas(Base):
    """1 linha por baixa (pagamento efetivo de uma parcela).

    Vem de /v1/financeiro/eventos-financeiros/parcelas/{id} → `baixas[]`.
    Uma parcela com pagamento parcial pode ter múltiplas baixas.
    Traz campos AUSENTES em /buscar: metodo_pagamento, data_pagamento real,
    conta destino, conciliado.
    """
    __tablename__ = "core_ca_baixas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_ca_baixas_external"),
        Index("ix_core_ca_baixas_tipo_data_pagamento", "tenant_id", "tipo", "data_pagamento"),
        Index("ix_core_ca_baixas_metodo_data", "tenant_id", "metodo_pagamento", "data_pagamento"),
        Index("ix_core_ca_baixas_parcela", "tenant_id", "parcela_external_id"),
        Index("ix_core_ca_baixas_conta", "tenant_id", "conta_financeira_external_id"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(64), nullable=False)
    parcela_external_id = Column(String(64), nullable=False)
    evento_external_id = Column(String(64), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())
    tipo = Column(String(20), nullable=True)            # RECEITA | DESPESA
    data_pagamento = Column(Date, nullable=True)
    data_vencimento = Column(Date, nullable=True)
    data_competencia = Column(Date, nullable=True)
    metodo_pagamento = Column(String(60), nullable=True)
    valor_pago = Column(Numeric(15, 2), nullable=True)
    valor_bruto = Column(Numeric(15, 2), nullable=True)
    valor_liquido = Column(Numeric(15, 2), nullable=True)
    multa = Column(Numeric(15, 2), nullable=True)
    juros = Column(Numeric(15, 2), nullable=True)
    desconto = Column(Numeric(15, 2), nullable=True)
    taxa = Column(Numeric(15, 2), nullable=True)
    conta_financeira_external_id = Column(String(64), nullable=True)
    conta_financeira_nome = Column(String(255), nullable=True)
    conta_financeira_banco = Column(String(60), nullable=True)
    conciliado = Column(Boolean, nullable=True)
    baixa_agendada = Column(Boolean, nullable=True)
    origem_referencia = Column(String(40), nullable=True)
    nsu = Column(String(60), nullable=True)
    pessoa_external_id = Column(String(64), nullable=True)


class CoreCaContasFinanceiras(Base):
    """1 linha por conta financeira (banco) — combina /v1/conta-financeira
    com /v1/conta-financeira/{id}/saldo-atual.
    """
    __tablename__ = "core_ca_contas_financeiras"
    __table_args__ = (
        *_common_args(__tablename__),
        Index("ix_core_ca_contas_financeiras_ativo", "tenant_id", "ativo"),
    )
    id, tenant_id, external_id, is_deleted, external_updated_at, created_at, updated_at = _common_cols()
    nome = Column(String(255), nullable=True)
    banco = Column(String(255), nullable=True)
    codigo_banco = Column(String(20), nullable=True)
    agencia = Column(String(50), nullable=True)
    numero = Column(String(50), nullable=True)
    tipo = Column(String(30), nullable=True)
    ativo = Column(Boolean, nullable=True)
    conta_padrao = Column(Boolean, nullable=True)
    possui_config_boleto = Column(Boolean, nullable=True)
    saldo_atual = Column(Numeric(15, 2), nullable=True)
    saldo_atualizado_em = Column(DateTime, nullable=True)


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
