import api from '@/services/api'
import type { SonIABullet, SonIAInsight, SonIAPagePublication } from './SonIAContext'

/**
 * Análise da SonIA — entry point chamado pelo FAB ao abrir.
 *
 * Fluxo:
 *  1. Tenta endpoint `GET /ai/insight?page_key=...&year=...&month=...`
 *     - 200 → usa a resposta da IA (DeepSeek ou Claude no backend)
 *     - 404 → backend não tem provedor de IA ou página não suportada
 *     - 4xx/5xx/rede → idem
 *  2. Fallback: usa `publication.data.insight` (heurística calculada na própria página)
 *  3. Se nada disponível → texto default acolhedor
 *
 * O `period` (year/month) vem do `publication.data.period`. Páginas com
 * PeriodSelector devem publicar isso; páginas "do dia" (Agenda, Início)
 * podem omitir — caímos pra mês atual.
 */

const SOURCE_HEURISTIC = 'Heurístico'

interface ApiInsightResponse {
  mood: SonIAInsight['mood']
  headline: string
  detail: string
  bullets?: { text: string; tone?: SonIABullet['tone'] }[]
  cta_href?: string | null
  cta_label?: string | null
  source: string
}

function apiToInsight(api: ApiInsightResponse): SonIAInsight {
  return {
    mood: api.mood,
    headline: api.headline,
    detail: api.detail,
    bullets: api.bullets?.map((b) => ({ text: b.text, tone: b.tone })),
    ctaHref: api.cta_href ?? undefined,
    ctaLabel: api.cta_label ?? undefined,
    source: api.source,
  }
}

function defaultInsight(pageTitle?: string): SonIAInsight {
  return {
    mood: 'curious',
    headline: pageTitle ? `Estou conhecendo "${pageTitle}".` : 'Estou conhecendo essa página.',
    detail:
      'Ainda estou aprendendo a ler tudo daqui. Em breve vou conseguir te trazer observações específicas. Pode contar comigo.',
    source: SOURCE_HEURISTIC,
  }
}

function emptyInsight(): SonIAInsight {
  return {
    mood: 'default',
    headline: 'Estou pronta pra te ajudar.',
    detail:
      'Abra uma página de análise (Financeiro, Comercial, Pacientes, Agenda...) e me chame de novo. Vou olhar o que está na tela e te trazer observações.',
    source: SOURCE_HEURISTIC,
  }
}

function localFallback(publication: SonIAPagePublication): SonIAInsight {
  const data = publication.data as { insight?: SonIAInsight } | undefined | null
  if (data?.insight) {
    return { source: SOURCE_HEURISTIC, ...data.insight }
  }
  return defaultInsight(publication.pageTitle)
}

export async function analyze(publication: SonIAPagePublication | null): Promise<SonIAInsight> {
  if (!publication) return emptyInsight()

  // Period: prioridade pra o que a página publicou; senão usa "hoje".
  const data = publication.data as { period?: { year: number; month: number } } | undefined | null
  const now = new Date()
  const year = data?.period?.year ?? now.getFullYear()
  const month = data?.period?.month ?? now.getMonth() + 1

  try {
    const res = await api.get<ApiInsightResponse>('/ai/insight', {
      params: { page_key: publication.pageKey, year, month },
    })
    return apiToInsight(res.data)
  } catch {
    // 404 (página não suportada / IA indisponível) ou erro transitório.
    // Cai pra heurística local sem mostrar erro ao usuário.
    return localFallback(publication)
  }
}
