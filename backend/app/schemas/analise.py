"""
Schemas dos dashboards segmentados (Sub-PR 20).

Estratégia: cada KPI traz MoM/YoY/sparkline/insight prontos do backend.
Frontend não calcula nada — só renderiza. Permite reuso do componente
KpiCard em todos os dashs (Financeiro/Comercial/Pacientes).
"""
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


# ── Comum entre todos os dashs ──────────────────────────────────


class PeriodInfo(BaseModel):
    year: int
    month: int
    year_month_key: str            # YYYY-MM
    label: str                     # "abril/2026"


class KpiCard(BaseModel):
    """KPI rico: valor + comparativos + sparkline + insight narrativo.

    O frontend renderiza um Card padronizado a partir desta estrutura.
    """
    value: float
    value_label: str               # formatado pra exibir (R$, %, número)

    # Comparativo Month-over-Month (vs mês anterior)
    mom_value: Optional[float] = None        # delta absoluto
    mom_pct: Optional[float] = None          # delta % (50.0 = +50%)
    mom_label: Optional[str] = None          # "+R$ 48k vs mar/26"

    # Comparativo Year-over-Year (vs mesmo mês ano anterior)
    yoy_value: Optional[float] = None
    yoy_pct: Optional[float] = None
    yoy_label: Optional[str] = None          # "+12% vs abr/25"

    # Tendência geral observada
    trend: Literal["up", "down", "flat"] = "flat"

    # 12 últimos meses pra sparkline (do mais antigo ao mais recente)
    sparkline_12m: List[float] = []

    # Frase narrativa curta — gerada por regras no backend.
    # Ex: "Acima da média de 6m. Crescendo há 3 meses consecutivos."
    insight: Optional[str] = None

    # Quando "menor é melhor" (inadimplência, churn) — frontend inverte cores
    is_inverse: bool = False

    # Mês parcial (mês corrente em andamento). Quando True, value reflete só o
    # acumulado até hoje. Frontend pode mostrar projeção e badge "(parcial X/Y)".
    is_partial: bool = False
    partial_progress: Optional[float] = None       # 0-1, fração do mês decorrida
    partial_days: Optional[int] = None             # dias decorridos (1-31)
    partial_days_in_month: Optional[int] = None    # total de dias do mês
    projected_value: Optional[float] = None        # valor projetado p/ fim do mês
    projected_label: Optional[str] = None          # "R$ 271k projetado"


# ── Financeiro ──────────────────────────────────────────────────


class RecebidoBreakdown(BaseModel):
    """Decomposição do Recebido (caixa) — útil pra auditoria contra Clinicorp.

    Mapeamento dos campos contra a coluna do PDF "Pagamentos e Comissões":
      - `liquido`  → coluna "Valor"        → SUM(core_payments.amount)
      - `bruto`    → coluna "Valor Total"  → SUM(core_payments.total_amount)
      - `taxas`    → coluna "Taxas/Descontos" → SUM(core_payments.fee)
      - `taxas_pct` = taxas / bruto * 100 (% perdido em maquininha/boleto)

    Filtra por `is_received=1` e mês de `received_date` (data de compensação).
    """
    liquido: float
    bruto: float
    taxas: float
    taxas_pct: float


class FinanceiroKpis(BaseModel):
    """4 KPIs principais do dashboard financeiro.

    Inadimplência foi movida para o dashboard de Fluxo de Caixa
    (`/financeiro`), onde o tema "saúde de recebíveis" é mais pertinente.
    """
    faturamento: KpiCard           # SUM(amount) WHERE is_approved=1 no mês
    conversao: KpiCard             # aprovados / gerados (% por valor)
    ticket_medio: KpiCard          # faturamento / aprovados
    recebido: KpiCard              # SUM(amount) WHERE is_received=1 no mês
    recebido_breakdown: RecebidoBreakdown   # bruto/líquido/taxas (mês corrente)


class FunilOrcamentos(BaseModel):
    """Funil completo: gerados → aprovados → pagos.

    "pagos" significa orçamentos cujo paciente teve PELO MENOS 1 pagamento
    associado no período observado. Aproximação válida sem `core_treatment_payments`.

    Conversão exposta em DUAS visões:
    - **Valor (R$)**: alinha com Clinicorp ERP (R$ aprovado / R$ total)
    - **Quantidade**: eficácia comercial por orçamento
    """
    gerados_qty: int
    gerados_amount: float
    aprovados_qty: int
    aprovados_amount: float
    pagos_qty: int
    pagos_amount: float
    # Conversões entre etapas — POR QUANTIDADE
    conversao_aprovacao_pct: float    # aprovados_qty / gerados_qty
    conversao_pagamento_pct: float    # pagos_qty / aprovados_qty
    # Conversões entre etapas — POR VALOR (R$) — principal/Clinicorp
    conversao_aprovacao_valor_pct: float       # aprovados_amount / gerados_amount
    conversao_pagamento_valor_pct: float       # pagos_amount / aprovados_amount
    # Comparativos com mês anterior
    aprovacao_mom_pct: Optional[float] = None             # MoM da % por qtd
    pagamento_mom_pct: Optional[float] = None
    aprovacao_valor_mom_pct: Optional[float] = None       # MoM da % por valor
    pagamento_valor_mom_pct: Optional[float] = None


class TopProfFaturamento(BaseModel):
    """Atendente ranqueado por faturamento dos orçamentos que registrou.

    `professional_external_id` em `fato_orcamentos` é o ATENDENTE (quem
    registrou o orçamento), não o médico que vai executar — tipicamente
    secretária/recepção. Para médico executante, ver `TopMedicoFaturamento`.
    """
    professional_external_id: int
    nome: str
    faturamento: float                # SUM aprovados
    valor_gerado: float               # SUM total gerado (aprovados + outros status)
    qtd_aprovados: int
    qtd_gerados: int
    taxa_conversao_pct: float         # qtd: aprovados/gerados
    taxa_conversao_valor_pct: float   # valor: faturamento/valor_gerado (Clinicorp)
    ticket_medio: float
    pct_total: float                  # % do faturamento total da clínica


class TopMedicoFaturamento(BaseModel):
    """Médico (dentist) ranqueado por faturamento dos procedimentos que executa.

    Agregação: SUM(`core_estimate_procedures.final_amount`) WHERE orçamento aprovado,
    agrupado por `dentist_external_id`. Procedimentos sem dentista são excluídos.
    """
    dentist_external_id: int
    nome: str
    faturamento: float                # SUM final_amount dos procedimentos aprovados
    qtd_procedimentos: int            # total de procedimentos aprovados
    qtd_orcamentos: int               # orçamentos distintos com algum procedimento dele
    ticket_medio_procedimento: float  # faturamento / qtd_procedimentos
    pct_total: float                  # % do faturamento médico total da clínica


class TopCategoriaFaturamento(BaseModel):
    """Categoria de procedimento ranqueada por faturamento aprovado."""
    categoria: str                    # nome do procedure_expertise_name
    faturamento: float
    qtd_procs: int                    # nº de procedimentos aprovados desta categoria
    pct_total: float
    ticket_medio: float               # faturamento / qtd_procs
    mom_pct: Optional[float] = None   # variação dessa categoria mês anterior


class MixPagamentoEnriched(BaseModel):
    """Mix de meios de pagamento com variação MoM."""
    forma_pagamento: str
    valor: float
    pct: float
    qtd_transacoes: int
    mom_pct: Optional[float] = None


class SaudeRecebiveis(BaseModel):
    """KPIs táticos de gestão de recebíveis."""
    tempo_medio_aprovacao_dias: Optional[float] = None    # gerado→aprovado
    tempo_medio_recebimento_dias: Optional[float] = None  # aprovado→1º pagamento
    inadimplencia_qty: int                                # parcelas em aberto
    inadimplencia_amount: float
    inadimplencia_60d_qty: int                            # vencidas 60+ dias
    inadimplencia_60d_amount: float
    inadimplencia_pct_total: Optional[float] = None       # % do faturamento aprovado


class FinanceiroEvolutionPoint(BaseModel):
    """1 ponto da evolution chart de 12 meses."""
    year_month_key: str               # YYYY-MM
    label: str                        # "abr/26"
    faturamento: float                # orçamentos aprovados no mês
    recebido: float                   # pagamentos confirmados no mês
    aprovados_qty: int


class PrazoBucket(BaseModel):
    """Faixa de número de parcelas — agrupa pagamentos por horizonte de recebimento."""
    label: str          # "1x à vista", "2-3x curto", etc.
    qtd_pagamentos: int
    valor: float
    ticket_medio: float
    pct_qtd: float      # % do total de pagamentos
    pct_valor: float    # % do valor total


class PrazoRecebimentoSection(BaseModel):
    """Distribuição do valor aprovado por número de parcelas combinadas.

    Responde: "Dos R$ X aprovados no mês, quanto vai em 1x, 5x, 12x...?"

    Cada linha de pagamento (parcela) é alocada ao bucket do seu próprio
    `installments_count`. Um fechamento com entrada 1x + parcelado 25x tem
    seu valor distribuído nos buckets correspondentes, sem agrupamento por
    header (que pode misturar formas/parcelas).

    Notas:
    - `qtd_pagamentos_total` = headers distintos no período. Os `qtd_pagamentos`
      por bucket podem somar mais que o total (header com plano misto aparece
      em mais de um bucket).
    - `prazo_medio_dias` é ponderado pelo valor das parcelas.
    """
    qtd_pagamentos_total: int
    valor_total: float
    pct_a_vista_qtd: float            # % dos pagamentos que são 1x
    pct_a_vista_valor: float          # % do valor que foi 1x
    prazo_medio_dias: float           # entre data do orçamento e vencimento
    ticket_medio_a_vista: float       # ticket médio dos pagamentos 1x
    ticket_medio_parcelado: float     # ticket médio dos pagamentos 2x+
    buckets: List[PrazoBucket]
    mom_a_vista_pct: Optional[float] = None  # variação MoM de pct_a_vista_valor (em pontos %)
    yoy_a_vista_pct: Optional[float] = None
    # Cobertura — valor_total cobre só as parcelas JÁ lançadas no plano de
    # pagamento. A Clinicorp gera o plano em partes (entrada hoje, restante
    # conforme paciente paga), então valor_total < faturamento aprovado.
    faturamento_aprovado: float = 0.0      # SUM(ce.amount) dos orçamentos APPROVED no mês
    qtd_sem_parcelas: int = 0              # nº de orçamentos aprovados sem nenhuma parcela em core_payments
    valor_sem_parcelas: float = 0.0        # SUM(ce.amount) desses orçamentos


class TaxaPorForma(BaseModel):
    """Custo de adquirência por forma de pagamento.

    Cruza `core_payments` (bruto agrupado por payment_form) com
    `core_summary_entries` (líquido por payment_form_characteristic_id) pra
    calcular a taxa efetiva que cada maquininha/banco cobrou.
    """
    forma_pagamento: str             # "Cartão de Crédito", "Cartão de Débito", "Boleto", "Pix", etc.
    bruto: float                     # SUM(core_payments.amount)
    liquido: float                   # SUM(core_summary_entries.amount) DEBIT/RECEIVED
    taxa: float                      # bruto - liquido
    taxa_pct: float                  # taxa / bruto * 100 (taxa efetiva DESSA forma)
    pct_volume: float                # bruto desta forma / bruto_total * 100
    qtd_transacoes: int
    is_estimated: bool = False       # True quando a taxa por forma vem de heurística (API não fatia)


class TaxasSection(BaseModel):
    """Custo de adquirência total + breakdown por forma de pagamento.

    Indicadores chave:
    - `taxa_global_pct`: total / bruto_total — média sobre TUDO (mascarada por Pix/Dinheiro)
    - `taxa_efetiva_pct`: total / bruto_com_taxa — taxa real cobrada pela maquininha
    - `economia_potencial_anual`: estimativa se 30% do volume de cartão crédito virasse Pix
    """
    taxas_total: float
    bruto_total: float
    bruto_com_taxa: float            # apenas formas que cobram taxa
    bruto_sem_taxa: float            # Pix + Dinheiro + Transferência (geralmente)
    taxa_global_pct: float           # taxas / bruto_total
    taxa_efetiva_pct: float          # taxas / bruto_com_taxa (RELEVANTE para negociação)
    por_forma: List[TaxaPorForma]
    mom_efetiva_pct: Optional[float] = None    # variação MoM de taxa_efetiva_pct (pp)
    yoy_efetiva_pct: Optional[float] = None
    economia_potencial_anual: float = 0.0      # = taxa_pct(crédito) * 30% * bruto(crédito) * 12
    is_estimated: bool = False                  # True = taxa por forma estimada (API não fatia por pf_id)


class PrazoAuditItem(BaseModel):
    """Linha de auditoria — uma parcela de um plano de pagamento."""
    treatment_external_id: int                  # = estimate.external_id (linka ao orçamento)
    payment_header_external_id: Optional[int]   # agrupa parcelas do mesmo fechamento
    patient_name: Optional[str]
    professional_name: Optional[str]            # responsável pelo orçamento
    estimate_date: Optional[str]                # YYYY-MM-DD
    estimate_amount: Optional[float]            # valor total do orçamento (referência)
    payment_form: Optional[str]                 # Pix, Cartão, Dinheiro…
    installment_number: Optional[int]           # 1, 2, 3…
    installments_count: Optional[int]           # total de parcelas
    amount: float                               # valor desta parcela
    due_date: Optional[str]                     # YYYY-MM-DD


class PrazoAuditResponse(BaseModel):
    period: PeriodInfo
    items: List[PrazoAuditItem]
    total_count: int                # total real (sem limit)
    returned_count: int             # qtd retornada (≤ limit)
    limit: int


# ── Auditoria por ORÇAMENTO (status financeiro) ─────────────────


class OrcamentoParcela(BaseModel):
    """1 parcela detalhada — embutida em OrcamentoStatusItem.

    Campos `is_confirmed`/`is_received`/`is_conferida` espelham as 4 fases
    do ciclo de pagamento Clinicorp (ver memória `reference_clinicorp_payment_phases`):
        Fase 1 — Lançada (linha existe)
        Fase 2 — Confirmada (operadora aprovou)
        Fase 3 — Recebida (dinheiro caiu na conta)
        Fase 4 — Conferida (financeiro conciliou com extrato)

    A API REST só retorna pagamentos que chegaram à Fase 4, então `is_conferida`
    tende a ser True em ~100% dos casos — mas o campo fica como referência
    visual da taxonomia.
    """
    payment_external_id: int
    payment_header_external_id: Optional[int] = None
    installment_number: Optional[int] = None
    installments_count: Optional[int] = None
    amount: float
    due_date: Optional[str] = None        # YYYY-MM-DD
    received_date: Optional[str] = None   # YYYY-MM-DD ou None se não pago
    payment_form: Optional[str] = None
    is_confirmed: bool                     # Fase 2 — operadora aprovou
    is_received: bool                      # Fase 3 — dinheiro caiu
    is_conferida: bool                     # Fase 4 — financeiro conciliou
    is_vencida: bool                       # !is_received AND due_date < hoje


class OrcamentoStatusItem(BaseModel):
    """1 orçamento aprovado com status financeiro consolidado.

    Status distingue 5 estados pra capturar a pegadinha do Clinicorp gerar
    plano de pagamento em partes (entrada lançada, resto fica pra depois):

    - sem_parcelas: Clinicorp ainda não lançou nenhuma parcela
    - nao_pago: tem parcelas, mas zero recebido
    - parcial: recebeu algo, há pendentes/vencidas
    - pago_lancado: 100% do lançado pago, MAS lançado < contratado (falta Clinicorp lançar mais)
    - pago_integral: cobertura total — pago == lançado == contratado
    """
    treatment_external_id: int
    patient_name: Optional[str] = None
    professional_name: Optional[str] = None
    estimate_date: Optional[str] = None
    contratado: float                # core_estimates.amount (header)
    lancado: float                   # SUM amount das parcelas geradas
    pago: float                      # SUM amount WHERE is_received=1
    parcelas_qty: int                # total de parcelas geradas (= len(parcelas))
    parcelas_pagas_qty: int          # is_received=1
    parcelas_pendentes_qty: int      # is_received=0 (inclui vencidas)
    parcelas_vencidas_qty: int       # is_received=0 AND due_date < hoje
    pct_pago_contratado: float       # pago / contratado * 100 (visão comercial real)
    pct_pago_lancado: float          # pago / lancado * 100 (visão do plano efetivo)
    status: str
    parcelas: List[OrcamentoParcela]


class OrcamentoStatusResponse(BaseModel):
    period: PeriodInfo
    items: List[OrcamentoStatusItem]
    # Contagens por status — pro frontend mostrar tabs/badges sem recomputar
    contagens: dict[str, int]
    # Totais agregados (R$ contratado / lançado / pago do conjunto inteiro)
    totais_contratado: float
    totais_lancado: float
    totais_pago: float


class DescontosSection(BaseModel):
    """Resumo de descontos concedidos sobre orçamentos APROVADOS no mês.

    Considera APENAS procedimentos com status='Aprovado' (que efetivamente serão executados).
    Procs com status='Orçamento' (sugeridos e não selecionados pelo paciente) são tratados
    como escopo reduzido, NÃO como desconto, e expostos separadamente em `escopo_nao_aprovado`.

    Decomposição matematicamente fechada:
      desconto_total = desconto_procedimento + desconto_negociacao
    - `desconto_procedimento`: ajuste explícito por procedimento (OriginalAmount → FinalAmount)
    - `desconto_negociacao`: residual; desconto extra negociado no fechamento do orçamento
      (já não inclui procedimentos retirados — esses estão em `escopo_nao_aprovado`)
    - `desconto_total`: original_amount_tabela - faturamento
    """
    qtd_orcamentos_aprovados: int
    qtd_procs_aprovados: int               # procs com status='Aprovado' nos estimates aprovados
    original_amount_tabela: float          # soma OriginalAmount dos procs aprovados
    faturamento: float                     # = header_amount aprovado (já no card de faturamento)
    desconto_total: float                  # tabela - faturamento
    desconto_total_pct: float              # % sobre tabela
    desconto_procedimento: float           # original - final dos procs aprovados
    desconto_procedimento_pct: float
    desconto_negociacao: float             # residual: desc_total - desc_procedimento
    desconto_negociacao_pct: float
    escopo_nao_aprovado: float             # informativo: SUM(final_amount) dos procs sugeridos mas NÃO aprovados
    mom_total_pct: Optional[float] = None  # variação MoM do desconto_total_pct (em pontos %)
    yoy_total_pct: Optional[float] = None  # variação YoY do desconto_total_pct (em pontos %)


class AnaliseFinanceiroResponse(BaseModel):
    """Resposta completa do GET /analytics/financeiro?year=Y&month=M."""
    period: PeriodInfo
    previous: PeriodInfo               # mês anterior (referência MoM)
    yoy: PeriodInfo                    # mesmo mês ano anterior (referência YoY)

    kpis: FinanceiroKpis
    funil: FunilOrcamentos
    descontos: DescontosSection
    prazos: PrazoRecebimentoSection
    taxas: TaxasSection

    mix_pagamento: List[MixPagamentoEnriched]
    top_profissionais: List[TopProfFaturamento]   # atendentes (registrantes)
    top_medicos: List[TopMedicoFaturamento]       # dentistas executantes
    top_categorias: List[TopCategoriaFaturamento]

    evolution: List[FinanceiroEvolutionPoint]   # 12 meses


# ── Comercial (Sub-PR 20c) ──────────────────────────────────────


class ConversaoBreakdown(BaseModel):
    """Decomposição dos pacientes atendidos por status de conversão no mês.

    Soma sempre = total_atendidos. Útil pra explicar o complemento dos 100%
    do KPI de conversão — não é "todos não fecharam", boa parte está em
    tratamento (já aprovou em mês anterior) ou são avulsos (sem orçamento
    em mês nenhum).
    """
    total_atendidos: int                # pacientes_unicos_efetivos do mês
    aprovou_no_mes: int                 # entram no numerador da conversão
    aprovou_no_mes_pct: float
    gerou_nao_aprovou: int              # gerou orçamento no mês mas não aprovou (em decisão)
    gerou_nao_aprovou_pct: float
    em_tratamento: int                  # sem orçamento no mês mas com aprovado em mês anterior
    em_tratamento_pct: float
    avulso_sem_orcamento: int           # NUNCA teve orçamento em mês nenhum (manutenção, retorno, avulso)
    avulso_sem_orcamento_pct: float
    historico_sem_aprov: int            # tem orçamento em mês anterior mas nunca aprovou (pendente/rejeitado antigo)
    historico_sem_aprov_pct: float


class ComercialKpis(BaseModel):
    """4 KPIs principais do dashboard comercial.

    Foco em VOLUME e EFICIÊNCIA OPERACIONAL — máquina de consultas/conversão.
    Ticket por consulta foi removido em 2026-05-08: leitura artificial (rateio
    de orçamentos por consulta) e duplicava a visão financeira sem agregar.
    """
    consultas: KpiCard                       # is_efetiva=1 (CHECKOUT — paciente atendido)
    absenteismo_pct: KpiCard                 # is_inverse: faltas / (efetivas + faltas)
    conversao_consulta_orcamento_pct: KpiCard  # pacientes atendidos com orçamento aprovado / pacientes atendidos
    conversao_breakdown: ConversaoBreakdown    # decomposição dos 100% do denominador
    pacientes_unicos: KpiCard                # pacientes distintos com is_efetiva=1


class FunilComercial(BaseModel):
    """Funil paciente atendido → orçamento → aprovação.

    Cardinalidade: TODOS os 3 níveis são por PACIENTE (não por evento).
    Mistura entre eventos e pacientes mascarava a leitura — ver auditoria
    em 2026-05-08. Conversão total bate com KPI "Conversão em orçamento".

    `total_consultas` é exibido como contexto de volume ("691 consultas em
    442 pacientes"), não entra em nenhum cálculo de %.
    """
    pacientes_atendidos: int                # pacientes distintos com is_efetiva=1
    total_consultas: int                    # nº de consultas efetivas (eventos) — só pra contexto
    com_orcamento_qty: int                  # pacientes atendidos com orçamento gerado no mês
    aprovados_qty: int                      # pacientes atendidos com orçamento aprovado no mês
    aprovados_amount: float                 # SUM amount dos aprovados
    # Taxas (todas paciente / paciente)
    taxa_oferta_pct: float                  # com_orcamento / pacientes_atendidos
    taxa_aprovacao_pct: float               # aprovados / com_orcamento
    taxa_conversao_total_pct: float         # aprovados / pacientes_atendidos (= KPI Conversão)
    # Tempo médio
    tempo_medio_consulta_aprov_dias: Optional[float] = None
    # MoM
    taxa_oferta_mom_pct: Optional[float] = None
    taxa_aprovacao_mom_pct: Optional[float] = None


class TopProcedimentoExecutado(BaseModel):
    """Procedimento executado ranqueado por volume."""
    procedure_name: str
    qtd_executados: int
    faturamento: float                      # SUM final_amount dos executados
    pct_volume: float                       # % do volume total
    ticket_medio: float                     # faturamento / qtd_executados


class TopEspecialidadeDemanda(BaseModel):
    """Especialidade com mais demanda (volume de procedimentos)."""
    especialidade: str
    qtd_procedimentos: int
    pct_volume: float                       # % do volume total
    faturamento: float                      # SUM final_amount


class TopProfissionalConsultas(BaseModel):
    """Profissional ranqueado por volume de consultas atendidas (CHECKOUT)."""
    professional_external_id: int
    nome: str
    qtd_consultas: int                      # is_efetiva=1 (CHECKOUT)
    qtd_faltas: int                         # is_falta=1 (MISSED)
    qtd_canceladas: int                     # is_canceled=1
    absenteismo_pct: float                  # faltas / (efetivas + faltas)
    pacientes_distintos: int                # distintos com is_efetiva=1
    ocupacao_pct: Optional[float] = None    # qtd / capacidade P95 estimada
    pct_volume: float                       # % do volume total da clínica


class MixCategoriaConsulta(BaseModel):
    """Mix de categorias de consulta (consulta/retorno/manutenção/...)."""
    categoria: str
    qtd: int
    pct: float
    canceladas: int
    absenteismo_pct: float
    mom_pct: Optional[float] = None


class OperacionalComercial(BaseModel):
    """Operacional reformulado em 3 blocos: problema → oportunidade → ações.

    Bloco 1 — Tempo perdido: horas das faltas + canceladas (mais palpável que R$).
    Bloco 2 — Aproveitamento de slots ociosos: % de encaixes sobre slots perdidos.
    Bloco 3 — Ações pendentes: contadores das tags operacionais do Clinicorp.

    Removido `cancelados_amount_estimado` (multiplicação artificial por ticket
    médio de consulta — métrica que não existe mais e que assumia que cada
    cancelamento valeria um atendimento cheio).
    """
    # Bloco 1 — Tempo perdido
    horas_perdidas: float                   # SUM duration_minutes em faltas+cancel / 60
    dias_equivalentes_8h: float             # horas_perdidas / 8 (1 dia útil de 1 prof)
    faltas_qty: int                         # is_falta=1 (separado pra mostrar composição)
    cancelados_qty: int                     # is_canceled=1

    # Bloco 2 — Aproveitamento de slots ociosos
    slots_perdidos: int                     # faltas + cancelados (quantos slots ficaram vazios)
    slots_recuperados_encaixe: int          # has_encaixe=1 (= encaixe_qty)
    taxa_aproveitamento_pct: float          # encaixe / slots_perdidos * 100

    # Bloco 3 — Ações pendentes (tags Clinicorp)
    remarcar_qty: int                       # has_remarcar=1
    retorno_pendente_qty: int               # has_retorno_pendente=1
    waitlist_qty: int                       # has_waitlist=1


class SaudeAgendaSection(BaseModel):
    """Decomposição do fluxo de agendamentos do mês.

    Universo `total` quebrado em 4 desfechos:
      efetivas (CHECKOUT)  — paciente atendido, base p/ procs/médicos/etc
      faltas (MISSED)      — paciente faltou, conta no absenteísmo clínico
      canceladas           — agendamento removido (qualquer motivo)
      indefinidas          — status NULL não-cancelado (recepção não atualizou)
      outros               — CONFIRMED, ARRIVED, IN_SESSION, LATE, CALL não-cancelados

    `absenteismo_clinico_pct` = faltas / (efetivas + faltas) — métrica clínica padrão.
    """
    total: int
    efetivas: int
    faltas: int
    canceladas: int
    indefinidas: int
    outros: int                              # total - (efetivas+faltas+cancel+indef)
    pct_efetivas: float
    pct_faltas: float
    pct_canceladas: float
    pct_indefinidas: float
    pct_outros: float
    absenteismo_clinico_pct: float          # faltas / (efetivas + faltas) * 100


class ComercialEvolutionPoint(BaseModel):
    """1 ponto da evolution chart 12m do comercial.

    Decomposição alinhada com a SaudeAgendaSection — empilhamento na ordem:
    efetivas (CHECKOUT) → faltas (MISSED) → canceladas → indefinidas (NULL).
    Total de agendamentos do mês = soma dos 4 (mais "outros" que é < 1%).
    """
    year_month_key: str
    label: str
    efetivas: int                 # consultas atendidas (CHECKOUT)
    faltas: int                   # paciente faltou (MISSED)
    canceladas: int               # is_canceled=1
    indefinidas: int              # status NULL não-cancelado
    pacientes_unicos: int         # contexto, não entra no empilhamento


class AnaliseComercialResponse(BaseModel):
    """Resposta de GET /analise/comercial?year=Y&month=M."""
    period: PeriodInfo
    previous: PeriodInfo
    yoy: PeriodInfo

    kpis: ComercialKpis
    funil: FunilComercial

    saude_agenda: SaudeAgendaSection
    top_procedimentos: List[TopProcedimentoExecutado]
    top_especialidades: List[TopEspecialidadeDemanda]
    top_profissionais: List[TopProfissionalConsultas]
    mix_categorias: List[MixCategoriaConsulta]
    operacional: OperacionalComercial

    evolution: List[ComercialEvolutionPoint]   # 12 meses


# ── Pacientes — /analise/pacientes ──────────────────────────────


class PacientesKpis(BaseModel):
    """4 KPIs principais — foco em retenção e oportunidade comercial.

    Pergunta-guia: "quem eu deveria estar ligando?"
    """
    pacientes_ativos: KpiCard           # is_active=1 (visita < 90d) — base viva
    taxa_recorrencia_pct: KpiCard       # % dos atendidos no mês que já eram base anterior
    ltv_medio: KpiCard                  # SUM pagamentos / pacientes ativos
    em_risco_qty: KpiCard               # is_inverse — bucket 90-180d (alvo de campanha)


class SaudeBaseSection(BaseModel):
    """Decomposição da base de pacientes por status de retenção.

    Buckets espelham a heurística do legado (curva de churn):
    - ativo: visita < 90d
    - em_risco: 90-180d sem visita
    - inativo: 180-365d sem visita
    - perdido: > 365d sem visita
    - sem_visita: never_seen (cadastrado mas nunca atendido)
    """
    total: int                          # tamanho da base inteira
    ativo_qty: int
    em_risco_qty: int
    inativo_qty: int
    perdido_qty: int
    sem_visita_qty: int
    ativo_pct: float
    em_risco_pct: float
    inativo_pct: float
    perdido_pct: float
    sem_visita_pct: float


class CurvaAbcItem(BaseModel):
    """1 classe da curva ABC de Pareto sobre LTV."""
    classe: str                         # 'A' | 'B' | 'C'
    qtd_pacientes: int
    faturamento: float                  # LTV total dessa classe
    pct_pacientes: float
    pct_faturamento: float


class NovosRecorrentesSection(BaseModel):
    """Novos vs Recorrentes no mês — enriquecido com R$ aprovado e ticket.

    Diferente do legado que mostrava só qty: aqui inclui R$ aprovado em
    orçamentos por grupo + ticket médio aprovado, pra responder "novos
    chegam mais lucrativos que recorrentes ou o contrário?".
    """
    total: int                          # pacientes únicos com is_efetiva no mês
    novos_qty: int                      # first_seen_at no mês
    recorrentes_qty: int                # first_seen_at < início do mês
    novos_amount_aprovado: float        # SUM ce.amount aprovado pelos novos no mês
    recorrentes_amount_aprovado: float  # idem dos recorrentes
    novos_ticket_medio: float           # amount / qty
    recorrentes_ticket_medio: float


class TopLtvPaciente(BaseModel):
    """Paciente entre os top 10 por LTV. Enriquecido com status de retenção."""
    external_id: int
    name: Optional[str] = None
    ltv: float                          # SUM amount is_received=1
    total_payments: int
    days_since_last_seen: Optional[int] = None
    bucket: str                         # ativo|em_risco|inativo|perdido|sem_visita
    qtd_consultas_total: int            # total_appointments


class ParaResgatarPaciente(BaseModel):
    """Paciente em risco/inativo com LTV alto — alvo prioritário de campanha."""
    external_id: int
    name: Optional[str] = None
    ltv: float
    days_since_last_seen: int
    bucket: str                         # em_risco | inativo
    mobile_phone: Optional[str] = None  # pra recepção ligar


class NovoPacienteMes(BaseModel):
    """Paciente que veio pela primeira vez no mês selecionado."""
    external_id: int
    name: Optional[str] = None
    first_seen_at: datetime
    professional_name: Optional[str] = None  # quem atendeu primeiro
    teve_orcamento: bool                # gerou pelo menos 1 orçamento no mês
    aprovou: bool                       # aprovou pelo menos 1 orçamento no mês
    valor_aprovado: float               # SUM ce.amount aprovado no mês


class OrcamentoPendentePaciente(BaseModel):
    """Orçamento gerado nos últimos 60 dias e ainda não aprovado/rejeitado.

    Status pendentes na Clinicorp: FOLLOWUP (em decisão) e OPEN (aberto).
    Janela ancorada em hoje — independente do filtro de mês do dashboard,
    porque é lista de ação imediata.
    """
    treatment_external_id: int          # id do orçamento (pra abrir na UI)
    patient_external_id: int
    patient_name: Optional[str] = None
    professional_name: Optional[str] = None  # quem registrou
    estimate_date: datetime
    days_ago: int                       # hoje - estimate_date
    amount: float
    status: str                         # FOLLOWUP | OPEN
    mobile_phone: Optional[str] = None  # pra recepção ligar


class PacientesEvolutionPoint(BaseModel):
    """1 ponto da evolution chart 12m — pacientes únicos por mês."""
    year_month_key: str
    label: str
    novos: int
    recorrentes: int


# ── Histórico do paciente (drawer drill-down) ───────────────────


class PacienteHistoricoConsulta(BaseModel):
    """1 linha do histórico de consultas no drawer."""
    appointment_external_id: int
    date: datetime
    professional_name: Optional[str] = None
    category: Optional[str] = None             # category_description original
    desfecho: str                              # efetiva | falta | cancelada | indefinida | outro


class PacienteHistoricoOrcamento(BaseModel):
    """1 linha do histórico de orçamentos no drawer."""
    treatment_external_id: int
    estimate_date: datetime
    professional_name: Optional[str] = None
    amount: float
    status: str                                # APPROVED | FOLLOWUP | OPEN | REJECTED


class PacienteDetalhe(BaseModel):
    """Cabeçalho do paciente no drawer."""
    external_id: int
    name: Optional[str] = None
    mobile_phone: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None               # M | F
    birth_date: Optional[date] = None
    age: Optional[int] = None                  # calculada hoje - birth_date
    bucket: str                                # ativo | em_risco | inativo | perdido | sem_visita
    days_since_last_seen: Optional[int] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


class PacienteMetricas(BaseModel):
    """Síntese numérica do paciente (vida toda)."""
    ltv: float                                 # SUM amount is_received=1
    qtd_consultas: int                         # total_appointments
    qtd_consultas_efetivas: int                # COUNT is_efetiva=1
    qtd_orcamentos: int                        # total_estimates
    qtd_orcamentos_aprovados: int              # COUNT status=APPROVED
    qtd_pagamentos: int                        # total_payments
    ticket_medio_orcamento: float              # SUM(amount)/qtd entre aprovados
    valor_orcado_pendente: float               # SUM amount FOLLOWUP+OPEN


class PacienteHistoricoResponse(BaseModel):
    """Resposta de GET /analise/pacientes/{pid}/historico."""
    paciente: PacienteDetalhe
    metricas: PacienteMetricas
    consultas: List[PacienteHistoricoConsulta]   # top 20 desc
    orcamentos: List[PacienteHistoricoOrcamento] # top 10 desc


# ── Captação & Origem (Frente A — HowDidMeet) ──────────────────


class CaptacaoOrigemItem(BaseModel):
    """1 canal de origem agrupado (Facebook/Instagram/Google/Indicado/Outros/...)."""
    canal: str                                # 'Facebook' | 'Instagram' | 'Google' | 'Indicação' | 'Outros' | etc.
    qtd_consultas: int                        # consultas com este canal
    qtd_pacientes: int                        # pacientes distintos atribuídos a este canal
    pct: float                                # qtd_consultas / total preenchido


class IndicacaoNominal(BaseModel):
    """Quem indicou (texto livre IndicationSource agrupado)."""
    nome_indicador: str
    qtd_consultas: int
    qtd_pacientes: int


class CaptacaoOrigemResponse(BaseModel):
    """Resposta de GET /analise/pacientes/captacao.

    Snapshot global (vida toda da clínica). Sem filtro de mês — preenchimento
    é tão raro (~0,1%) que cortar por período eliminaria a base.
    """
    total_consultas: int                      # total de appointments
    total_com_origem: int                     # com how_did_meet preenchido
    pct_preenchimento: float                  # total_com_origem / total_consultas * 100
    canais: List[CaptacaoOrigemItem]          # distribuição dos preenchidos
    indicacoes_nominais: List[IndicacaoNominal]  # top "Indicado por <nome>"


class AnalisePacientesResponse(BaseModel):
    """Resposta de GET /analise/pacientes?year=Y&month=M."""
    period: PeriodInfo
    previous: PeriodInfo
    yoy: PeriodInfo

    kpis: PacientesKpis
    saude_base: SaudeBaseSection
    curva_abc: List[CurvaAbcItem]
    novos_recorrentes: NovosRecorrentesSection
    top_ltv: List[TopLtvPaciente]
    para_resgatar: List[ParaResgatarPaciente]
    orcamentos_pendentes: List[OrcamentoPendentePaciente]
    novos_do_mes: List[NovoPacienteMes]

    evolution: List[PacientesEvolutionPoint]   # 12 meses
