import type { SonIAInsight, SonIAPagePublication } from './SonIAContext'

/**
 * Análise heurística por página. Hoje cada página passa `data.insight`
 * pronto (regra simples no front); na Fase 7 substituímos por chamada
 * `/ai/insight?page={pageKey}` no backend, mantendo a mesma interface.
 */

const SOURCE_HEURISTIC = 'Heurístico'

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

/** Entry point — chamado pelo FAB ao abrir. */
export function analyze(publication: SonIAPagePublication | null): SonIAInsight {
  if (!publication) return emptyInsight()
  const data = publication.data as { insight?: SonIAInsight } | undefined | null
  if (data && data.insight) {
    return { source: SOURCE_HEURISTIC, ...data.insight }
  }
  return defaultInsight(publication.pageTitle)
}
