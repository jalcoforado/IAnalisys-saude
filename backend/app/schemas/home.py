"""Schemas do Cockpit Operacional (HomePage personalizada por role)."""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class AppointmentTagBrief(BaseModel):
    name: str
    color: Optional[str] = None
    tag_class: Optional[str] = None      # waitlist|encaixe|remarcar|lembrete|...


class AgendaItem(BaseModel):
    external_id: str
    paciente_external_id: Optional[int]
    paciente_nome: str
    paciente_birth_date: Optional[date] = None
    paciente_gender: Optional[str] = None  # 'M' | 'F' | None
    profissional_external_id: Optional[int]
    profissional_nome: Optional[str]
    horario: Optional[str]               # HH:MM
    categoria: str
    category_color: Optional[str] = None
    category_group: Optional[str] = None  # consulta|retorno|manutencao|...
    duration_minutes: Optional[int] = None
    # Status do appointment no Clinicorp (CONFIRMED, ARRIVED, IN_SESSION,
    # CHECKOUT, MISSED, LATE, CALL, PENDING_MATERIAL ou None=Agendado default)
    status_type: Optional[str] = None
    status_description: Optional[str] = None
    status_color: Optional[str] = None
    # 18g: risco de no-show (0–100). Calculado on-the-fly pelo _risk no
    # backend. None quando não há base pra calcular (fim de dia, paciente
    # sem id, etc).
    risco_pct: Optional[int] = None
    risco_razao: Optional[str] = None
    # B: tags operacionais (Aguardado vaga, Encaixe, Lembrete etc) aplicadas
    # no Clinicorp. Lista pode vir vazia. Apenas tags com tag_class != 'outro'
    # são incluídas pra evitar poluir UI com tags ad-hoc raras.
    tags: List["AppointmentTagBrief"] = []


class CapacityProfBucket(BaseModel):
    """Capacidade × ocupação de um profissional individual no dia."""
    professional_external_id: int
    professional_nome: Optional[str]
    consultas_hoje: int
    consultas_teto_p95: int
    ocupacao_pct: int                    # 0–100, arredondado pra evitar ruído visual


class EncaixeSlot(BaseModel):
    """Janela vaga >= 30min entre duas consultas do mesmo profissional."""
    professional_external_id: int
    professional_nome: Optional[str]
    inicio: str                          # HH:MM
    fim: str                             # HH:MM
    duracao_min: int


class CapacitySection(BaseModel):
    """Camada 1: capacidade da clínica baseada em histórico (P95 90d).

    P95 (e não MAX) evita outlier de feirão/promoção distorcer 100%. Quando
    há menos de 30 dias de histórico, retorna placeholders sem teto definido.
    """
    historico_dias: int                  # janela de cálculo (default 90)
    historico_dias_efetivo: int          # quantos dias TÊM dado nessa janela

    # Capacidade total da clínica
    consultas_teto_p95: int              # P95 do total/dia
    consultas_hoje: int
    consultas_ocupacao_pct: int          # 0–100

    horas_cadeira_teto_p95: int          # em minutos (P95 da soma duration/dia)
    horas_cadeira_hoje: int              # em minutos
    horas_cadeira_ocupacao_pct: int

    # Por profissional (top com folga maior — quem pode receber encaixe)
    profs_com_folga: List[CapacityProfBucket]

    # Janelas vagas >= 30min identificadas na agenda do dia
    encaixes: List[EncaixeSlot]
    encaixe_total_min: int               # soma das durações dos encaixes


class RiskTopPatient(BaseModel):
    """Paciente do dia em destaque por risco de não comparecer."""
    paciente_external_id: int
    paciente_nome: str
    horario: Optional[str]
    profissional_nome: Optional[str]
    risco_pct: int                       # 0–100
    no_show_rate_pct: int                # taxa histórica observada (0–100)
    total_historico: int                 # quantas consultas anteriores serviram de base
    razao: str                           # rótulo curto: "Faltou 3 das últimas 5",
                                         # "1ª consulta", "Não confirmou", etc


class RiskSection(BaseModel):
    """Camada 2: risco de no-show da agenda do dia.

    Heurística sem ML — combina taxa histórica do paciente com baseline
    da clínica via média ponderada (peso = min(1, n/5)). Pacientes sem
    histórico recebem baseline + ajuste de "1ª consulta".
    """
    historico_dias: int                  # janela base (90 default)
    baseline_pct: int                    # % histórica de faltas da clínica (0–100)
    consultas_avaliadas: int             # quantas consultas tiveram risco calculado
    faltas_esperadas_min: int            # intervalo previsto: piso
    faltas_esperadas_max: int            # intervalo previsto: teto
    pacientes_alto_risco: List[RiskTopPatient]


class StrategicDayKPIs(BaseModel):
    """Resumo de 1 dia pra cards estratégicos da HomePage."""
    date_iso: str
    label: str                           # "Hoje" | "Amanhã" | "Depois"
    is_today: bool
    total: int
    ocupacao_pct: int                    # % do P95 da clínica
    faltas_esperadas_min: int
    faltas_esperadas_max: int
    confirmados: int                     # status_type=CONFIRMED
    confirmados_pct: int                 # entre os ainda pendentes
    riscos_altos: int                    # # pacientes com risco >= 30%
    encaixe_min: int                     # min total de janelas livres
    horas_cadeira_hoje: int              # min agendados


class StrategicOverview(BaseModel):
    """Visão estratégica consolidada (hoje + 2 dias) — payload da HomePage do dono."""
    days: List[StrategicDayKPIs]
    total_3d: int                        # consultas somadas dos 3 dias
    faltas_esperadas_3d_min: int
    faltas_esperadas_3d_max: int
    encaixe_total_3d_min: int            # janela livre somada nos 3 dias
    waitlist_3d: int                     # pacientes na lista de espera (Aguardado vaga) 3d
    encaixe_3d: int                      # marcações de Encaixe explícito 3d
    top_pacientes_risco: List[RiskTopPatient]  # top 5 consolidado
    top_profs_ociosos: List[CapacityProfBucket]  # top 5 com mais folga em algum dos 3 dias
    baseline_pct: int                    # baseline da clínica (referência única)


class WaitlistItem(BaseModel):
    """Paciente aguardando vaga / encaixe (tag Aguardado vaga ou Encaixe)."""
    appointment_external_id: str
    paciente_external_id: Optional[int]
    paciente_nome: str
    profissional_external_id: Optional[int]
    profissional_nome: Optional[str]
    horario: Optional[str]               # HH:MM (vaga tentativa atual)
    appointment_date_iso: str            # YYYY-MM-DD da vaga tentativa
    is_waitlist: bool                    # tag "Aguardado vaga"
    is_encaixe: bool                     # tag "Encaixe"
    dias_aguardando: int                 # dias desde quando a tag foi aplicada
    tag_color: Optional[str] = None


class WaitlistSection(BaseModel):
    """Camada B: lista de espera baseada nas tags do Clinicorp."""
    total: int
    waitlist_count: int                  # só "Aguardado vaga"
    encaixe_count: int                   # só "Encaixe"
    items: List[WaitlistItem]


class AgendaSection(BaseModel):
    date_iso: str                        # YYYY-MM-DD que está sendo mostrado
    is_today: bool                       # se está mostrando hoje ou fallback
    total: int
    horarios_ocupados: int               # qtd consultas ANTES de agora (já aconteceram)
    proximas: int                        # qtd consultas DEPOIS de agora
    items: List[AgendaItem]
    capacity: Optional[CapacitySection] = None  # 18f: análise de capacidade
    risk: Optional[RiskSection] = None          # 18g: risco de no-show
    waitlist: Optional[WaitlistSection] = None  # B: lista de espera por tags


class RecallItem(BaseModel):
    paciente_external_id: int
    paciente_nome: str
    qtd_consultas: int
    intervalo_medio_dias: int
    dias_desde_ultima: int
    atraso_relativo: float               # dias_desde / intervalo_medio
    ultima_consulta_iso: str
    total_payments: int                  # nº de pagamentos histórico (proxy de LTV)


class RecallSection(BaseModel):
    total_elegiveis: int                 # quantos atendem a heurística
    items: List[RecallItem]              # top N


class OrcamentoParadoItem(BaseModel):
    external_id: str
    paciente_external_id: Optional[int]
    paciente_nome: str
    profissional_nome: Optional[str]
    amount: float
    dias_aprovado: int                   # dias desde aprovação
    data_aprovacao_iso: str


class OrcamentosParadosSection(BaseModel):
    total: int
    valor_total: float
    items: List[OrcamentoParadoItem]


class InadimplenciaCriticaItem(BaseModel):
    parcela_external_id: str
    pessoa_nome: str
    categoria: Optional[str]
    valor_em_aberto: float
    dias_atraso: int
    data_vencimento_iso: str


class InadimplenciaCriticaSection(BaseModel):
    total: int
    valor_total: float
    items: List[InadimplenciaCriticaItem]


class ResumoDiaSection(BaseModel):
    entradas_previstas: float            # fato_caixa tipo=RECEITA, vence hoje
    saidas_previstas: float              # fato_caixa tipo=DESPESA, vence hoje
    saldo_previsto: float                # entradas - saidas
    qtd_parcelas_hoje: int


class TopProfissionalSemanaItem(BaseModel):
    external_id: int
    nome: str
    valor_aprovado: float
    qtd_aprovados: int


class TopProfsSemanaSection(BaseModel):
    inicio_iso: str                      # segunda-feira da semana atual
    fim_iso: str                         # domingo
    items: List[TopProfissionalSemanaItem]


class PendenciaItem(BaseModel):
    """Paciente com tag operacional pendente (orçamento a contatar, retorno
    pendente, remarcação, etc). Usado no PendenciasCard."""
    appointment_external_id: str
    paciente_external_id: Optional[int]
    paciente_nome: str
    profissional_nome: Optional[str]
    appointment_date_iso: Optional[str]  # YYYY-MM-DD da última consulta da tag
    horario: Optional[str]
    tag_name: str                        # nome cru da tag no Clinicorp
    tag_class: str                       # classe semântica
    dias_aplicada: int                   # dias desde quando a tag foi posta


class PendenciaBucket(BaseModel):
    tag_class: str                       # orcamento_pendente|retorno_pendente|remarcar|...
    label: str
    total: int
    items: List[PendenciaItem]           # top 5 mais antigos


class PendenciasOperacionaisSection(BaseModel):
    """Camada C: visão consolidada de tags operacionais que exigem ação.
    Filtra automaticamente classes de "ação pendente" (não inclui
    `financeiro_conferido` que é sinal de OK, nem `outro`)."""
    total: int                           # total de tags pendentes (todas classes)
    buckets: List[PendenciaBucket]       # uma por classe não-vazia, ordenadas por total DESC


class HomeDashboardResponse(BaseModel):
    """Cockpit. Cards são None quando o role não acessa essa seção."""
    role: str
    role_label: str                      # 'Operações' | 'Financeiro' | etc.
    user_full_name: str
    today_iso: str
    agenda: Optional[AgendaSection] = None
    recall: Optional[RecallSection] = None
    orcamentos_parados: Optional[OrcamentosParadosSection] = None
    inadimplencia_critica: Optional[InadimplenciaCriticaSection] = None
    resumo_dia: Optional[ResumoDiaSection] = None
    top_profs_semana: Optional[TopProfsSemanaSection] = None
    pendencias: Optional[PendenciasOperacionaisSection] = None
