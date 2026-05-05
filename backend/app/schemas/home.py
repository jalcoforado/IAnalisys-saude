"""Schemas do Cockpit Operacional (HomePage personalizada por role)."""
from typing import List, Optional

from pydantic import BaseModel


class AgendaItem(BaseModel):
    external_id: str
    paciente_external_id: Optional[int]
    paciente_nome: str
    profissional_external_id: Optional[int]
    profissional_nome: Optional[str]
    horario: Optional[str]               # HH:MM
    categoria: str
    category_color: Optional[str] = None
    duration_minutes: Optional[int] = None


class AgendaSection(BaseModel):
    date_iso: str                        # YYYY-MM-DD que está sendo mostrado
    is_today: bool                       # se está mostrando hoje ou fallback
    total: int
    horarios_ocupados: int               # qtd consultas ANTES de agora (já aconteceram)
    proximas: int                        # qtd consultas DEPOIS de agora
    items: List[AgendaItem]


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
