"""Schemas do dashboard financeiro (Conta Azul / fato_caixa)."""
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.dashboard import PeriodInfo


class FinanceiroKpis(BaseModel):
    entradas: float                   # SUM(valor_pago_rateado WHERE tipo=RECEITA)
    saidas: float                     # SUM(valor_pago_rateado WHERE tipo=DESPESA)
    saldo_liquido: float              # entradas - saidas
    a_receber: float                  # SUM(valor_em_aberto_rateado WHERE tipo=RECEITA)
    a_pagar: float                    # SUM(valor_em_aberto_rateado WHERE tipo=DESPESA)
    inadimplencia_pct: float          # vencidos receita / total receita * 100
    qtd_parcelas_vencidas: int
    # Encargos financeiros das baixas detalhadas (juros + multa - desconto).
    # Não estão em fato_caixa (vêm só de /parcelas/{id}); o PDF do CA soma esses
    # valores no total do mês — sem isso, há discrepância de uns ~R$ 2k em abr/26.
    encargos_entradas: float          # SUM(juros+multa-desconto) RECEITA — vencimento no mês
    encargos_saidas: float            # SUM(juros+multa-desconto) DESPESA — vencimento no mês


class CategoriaItem(BaseModel):
    external_id: Optional[str]
    nome: str
    total: float
    pct: float                        # % do tipo (entrada ou saída)


class CentroCustoItem(BaseModel):
    external_id: Optional[str]
    nome: str
    entradas: float
    saidas: float
    saldo: float


class StatusMixItem(BaseModel):
    status: str                       # 'pago'|'em_aberto'|'vencido'
    label_pt: str                     # 'Pago'|'Em aberto'|'Vencido'
    qtd: int
    total: float


class FinanceiroEvolutionPoint(BaseModel):
    year_month_key: str               # 'YYYY-MM'
    label_pt: str                     # 'Out/25'
    entradas: float
    saidas: float
    saldo: float                      # entradas - saidas (mês isolado, não cumulativo)


class ContaBancariaItem(BaseModel):
    """1 conta financeira com saldo atual."""
    external_id: str
    nome: str
    banco: Optional[str]
    codigo_banco: Optional[str]
    tipo: Optional[str]               # CONTA_CORRENTE | APLICACAO | CAIXINHA | ...
    saldo_atual: float
    ativo: bool
    is_banco_real: bool               # False pra CAIXINHA / NAO_BANCO (cofres contábeis)


class SaldosBancariosBlock(BaseModel):
    """Bloco do card "Saldo bancário" — separa bancos reais de caixinhas/cofres.

    "Bancos reais" = `tipo` em (CONTA_CORRENTE, APLICACAO, POUPANCA) — o que
    realmente está em instituição financeira e movimenta caixa.

    "Caixinhas/cofres" = `banco` = "NAO_BANCO" ou `tipo` = "CAIXINHA" — são
    registros contábeis internos (cofre da loja, controles), não bancos.
    """
    saldo_bancos: float               # soma só dos ativos com is_banco_real=True
    saldo_caixinhas: float            # soma das caixinhas/cofres (separado)
    qtd_bancos_ativos: int
    qtd_caixinhas_ativas: int
    qtd_contas_total: int
    atualizado_em: Optional[str]      # ISO datetime do último refresh
    contas: List[ContaBancariaItem]


class DreCategoriaItem(BaseModel):
    """Folha do DRE — categoria_financeira plana com valor no mês."""
    external_id: str
    nome: str
    total: float                           # SUM(valor_pago_rateado) no mês
    pct_subgrupo: float                    # % do total do subgrupo pai


class DreSubgrupoItem(BaseModel):
    """Subgrupo DRE (nível 1) — ex: '01.1 Receita de Vendas'."""
    external_id: str
    descricao: str
    codigo: Optional[str]
    posicao: Optional[int]
    qtd_categorias: int
    total: float                          # SUM(valor_pago_rateado) no mês
    categorias: List[DreCategoriaItem] = []  # 3º nível de drill (lazy-loaded no overview)


class DreGrupoItem(BaseModel):
    """Grupo DRE raiz com código (ex: '01 Receitas Operacionais').

    Totalizadores sem código (Receita Líquida, Margem de Contribuição etc)
    são omitidos por enquanto — são linhas calculadas do DRE clássico,
    sem categorias_financeiras vinculadas.
    """
    external_id: str
    descricao: str
    codigo: str
    posicao: Optional[int]
    total: float                          # somatório das folhas dentro do grupo
    subgrupos: List[DreSubgrupoItem]


class DreBlock(BaseModel):
    """Bloco DRE estruturado do mês — receitas e despesas agrupadas
    pelos nós raiz da árvore Conta Azul (16 raízes, 8 com código)."""
    grupos: List[DreGrupoItem]
    total_classificado: float             # SUM(grupos.total)
    total_nao_classificado: float         # fato_caixa sem categoria_external_id em links


class MetodoPagamentoItem(BaseModel):
    """1 método de pagamento (PIX, BOLETO, CARTAO_CREDITO, ...)."""
    metodo: str                       # chave canônica do CA
    label: str                        # tradução PT-BR
    qtd_baixas: int
    valor_total: float
    pct_valor: float                  # % do valor total das baixas no período


class MetodosPagamentoBlock(BaseModel):
    """Distribuição "Onde caiu o dinheiro" — só receitas (entradas).

    Baseado em core_ca_baixas (detalhamento /parcelas/{id}). Mostra mix
    de PIX/Cartão/Boleto/Outros. Se não houver baixas detalhadas no período,
    retorna lista vazia + flag pra UI mostrar CTA "Detalhar parcelas".
    """
    metodos: List[MetodoPagamentoItem]
    qtd_total: int
    valor_total: float
    cobertura_pct: float              # % das parcelas pagas que têm baixa detalhada
    pendentes_detalhamento: int       # quantas parcelas pagas sem detalhe


class ContaDestinoItem(BaseModel):
    """1 conta destino (em qual banco caiu o dinheiro)."""
    external_id: Optional[str]
    nome: str
    banco: Optional[str]
    qtd_baixas: int
    valor_total: float
    pct_valor: float


class ConciliacaoBlock(BaseModel):
    """% das baixas conciliadas com extrato bancário do CA."""
    qtd_total: int
    qtd_conciliadas: int
    qtd_nao_conciliadas: int
    pct_conciliado: float
    valor_conciliado: float
    valor_nao_conciliado: float
    contas_destino: List[ContaDestinoItem]   # top contas destino das baixas


class TransferenciaFluxoItem(BaseModel):
    """1 fluxo entre contas (origem → destino) com volume agregado."""
    origem_external_id: Optional[str]
    origem_nome: str
    origem_banco: Optional[str]
    destino_external_id: Optional[str]
    destino_nome: str
    destino_banco: Optional[str]
    qtd: int
    valor_total: float


class TransferenciasBlock(BaseModel):
    """Movimentação interna entre contas no mês — não é receita nem despesa.

    Mostra volume + top fluxos para o card "Transferências internas".
    """
    qtd: int
    valor_total: float
    qtd_contas_origem: int
    qtd_contas_destino: int
    fluxos: List[TransferenciaFluxoItem]   # top fluxos por valor


class FinanceiroOverviewResponse(BaseModel):
    period: PeriodInfo
    previous: PeriodInfo
    kpis: FinanceiroKpis
    kpis_previous: FinanceiroKpis     # mesmo objeto pro mês anterior, pra MoM
    saldos_bancarios: SaldosBancariosBlock
    dre: DreBlock
    metodos_pagamento: MetodosPagamentoBlock
    conciliacao: ConciliacaoBlock
    transferencias: TransferenciasBlock
    top_receitas: List[CategoriaItem]
    top_despesas: List[CategoriaItem]
    centros_custo: List[CentroCustoItem]
    status_mix: List[StatusMixItem]
    evolution: List[FinanceiroEvolutionPoint]
