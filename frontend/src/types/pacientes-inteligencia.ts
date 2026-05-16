// Tipos da página /pacientes/inteligencia (espelho de
// backend/app/schemas/pacientes_inteligencia.py)

export interface AcuraciaPaciente {
  paciente_external_id: number
  paciente_nome: string
  data: string
  risco_pct: number
  bucket: 'alto' | 'medio' | 'baixo'
  razao: string
  realmente_faltou: boolean
}

export interface AcuraciaBucket {
  bucket: 'alto' | 'medio' | 'baixo'
  total: number
  faltou: number
  veio: number
  taxa_falta_pct: number
}

export interface AcuraciaSection {
  appointments_avaliados: number
  baseline_pct: number
  acuracia_pct: number
  precisao_alto_pct: number
  recall_alto_pct: number
  buckets: AcuraciaBucket[]
  matriz: number[][]   // 2x3: [[alto_falta, medio_falta, baixo_falta], [alto_veio, medio_veio, baixo_veio]]
  acertos_alto_risco: AcuraciaPaciente[]
  escapes: AcuraciaPaciente[]
}

export interface TopFaltosoItem {
  paciente_external_id: number
  paciente_nome: string
  faltas: number
  atendimentos: number
  total: number
  taxa_falta_pct: number
  ultima_falta: string | null
}

export interface RetencaoBucket {
  janela_dias: number
  elegiveis: number
  retornaram: number
  taxa_pct: number
}

export interface RetencaoSection {
  buckets: RetencaoBucket[]
}

export interface EvasaoPaciente {
  paciente_external_id: number
  paciente_nome: string
  visitas_12m: number
  ultima_visita: string
  dias_sem_voltar: number
}

export interface HeatmapCelula {
  dow: number   // 0=segunda ... 6=domingo
  hora: number  // 0..23
  total: number
  faltas: number
  taxa_falta_pct: number
}

export interface HeatmapSection {
  celulas: HeatmapCelula[]
  total_global: number
  faltas_global: number
}

export interface EficaciaConfirmacao {
  com_lembrete_total: number
  com_lembrete_faltas: number
  com_lembrete_taxa_pct: number
  sem_lembrete_total: number
  sem_lembrete_faltas: number
  sem_lembrete_taxa_pct: number
  diferenca_pp: number
  cobertura_lembrete_pct: number
}

export interface InteligenciaPacientesResponse {
  periodo_dias: number
  gerado_em: string
  acuracia: AcuraciaSection
  top_faltosos: TopFaltosoItem[]
  retencao: RetencaoSection
  evasao_risco: EvasaoPaciente[]
  heatmap: HeatmapSection
  eficacia_confirmacao: EficaciaConfirmacao
}
