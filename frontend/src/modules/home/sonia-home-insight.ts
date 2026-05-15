/**
 * Gera um insight aleatório da SonIA pra a home (MY-Analisys).
 *
 * Princípio: a SonIA só comenta sobre o que o usuário ESCOLHEU mostrar no
 * painel. Cada widget tem um pool próprio de "frases observáveis" e só
 * contribui se estiver no layout salvo do user. Bullets do pool consolidado
 * são embaralhados — cada visita traz uma seleção diferente.
 */
import type { SonIAInsight } from '@/components/sonia/SonIAContext'
import type { HomeDashboardResponse } from '@/types/home'

type Bullet = NonNullable<SonIAInsight['bullets']>[number]

const fmtBRL = (n: number): string => {
  if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `R$ ${Math.round(n / 1_000)}k`
  return `R$ ${n.toFixed(0)}`
}

const fmtN = (n: number): string => new Intl.NumberFormat('pt-BR').format(n)

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function pick<T>(arr: T[]): T | null {
  if (arr.length === 0) return null
  return arr[Math.floor(Math.random() * arr.length)]
}

const HEADLINES_NEUTRAL = [
  'Olhei o painel com calma.',
  'Dei uma passada nas pendências.',
  'Aqui está o que reparei.',
  'Trouxe algumas observações.',
  'Olhei rapidinho o que está aberto.',
]

const HEADLINES_ALERT = [
  'Tem um ponto que vale uma olhada.',
  'Achei algo que merece atenção.',
  'Queria te contar uma coisa que vi.',
]

// Pools de bullets por widget. Cada função retorna 0+ bullets baseada nos
// dados disponíveis. Só widgets presentes no layout do user contribuem.
const BULLETS_BY_WIDGET: Record<string, (data: HomeDashboardResponse) => Bullet[]> = {
  agenda_summary: (d) =>
    d.agenda
      ? [{ text: `Hoje a clínica tem ${fmtN(d.agenda.total)} consultas marcadas.`, tone: 'neutral' }]
      : [],

  agenda_strategic: (d) =>
    d.agenda
      ? [{ text: `Hoje são ${fmtN(d.agenda.total)} consultas — vale conferir a estratégia de 3 dias.`, tone: 'neutral' }]
      : [],

  recall: (d) => {
    if (!d.recall || d.recall.total_elegiveis === 0) return []
    const out: Bullet[] = [
      {
        text: `${fmtN(d.recall.total_elegiveis)} pacientes elegíveis pra recall — vinham regularmente e estão atrasados.`,
        tone: d.recall.total_elegiveis > 50 ? 'warning' : 'neutral',
      },
    ]
    const top = d.recall.items[0]
    if (top) {
      out.push({
        text: `O mais atrasado é ${top.paciente_nome.split(' ')[0]} — ${top.dias_desde_ultima}d sem visita (vinha a cada ${top.intervalo_medio_dias}d).`,
        tone: 'warning',
      })
    }
    return out
  },

  pendencias: (d) =>
    d.pendencias && d.pendencias.total > 0
      ? [{
          text: `${fmtN(d.pendencias.total)} pendências operacionais sinalizadas no Clinicorp.`,
          tone: d.pendencias.total > 500 ? 'warning' : 'neutral',
        }]
      : [],

  orcamentos_parados: (d) =>
    d.orcamentos_parados && d.orcamentos_parados.total > 0
      ? [{
          text: `${fmtN(d.orcamentos_parados.total)} orçamentos aprovados parados, somando ${fmtBRL(d.orcamentos_parados.valor_total)}.`,
          tone: 'warning',
        }]
      : [],

  inadimplencia_critica: (d) =>
    d.inadimplencia_critica && d.inadimplencia_critica.total > 0
      ? [{
          text: `Inadimplência crítica: ${fmtN(d.inadimplencia_critica.total)} parcelas (${fmtBRL(d.inadimplencia_critica.valor_total)}) vencidas há mais de 60 dias.`,
          tone: d.inadimplencia_critica.total > 100 ? 'negative' : 'warning',
        }]
      : [],

  top_profs: (d) => {
    if (!d.top_profs_semana || d.top_profs_semana.items.length === 0) return []
    const top = d.top_profs_semana.items[0]
    const out: Bullet[] = [{
      text: `${top.nome.split(' ')[0]} lidera os aprovados da semana com ${fmtBRL(top.valor_aprovado)}.`,
      tone: 'positive',
    }]
    if (d.top_profs_semana.items.length >= 3) {
      const total = d.top_profs_semana.items.reduce((s, p) => s + p.valor_aprovado, 0)
      out.push({
        text: `Os top profissionais da semana somam ${fmtBRL(total)} em aprovados.`,
        tone: 'positive',
      })
    }
    return out
  },
}

/**
 * @param data resposta de /home/dashboard
 * @param widgetIds widgets presentes no layout do user. Bullets só são
 *   adicionadas se o widget estiver na lista. Se vazio, retorna mensagem
 *   genérica de "sem widgets ainda".
 */
export function buildHomeInsight(
  data: HomeDashboardResponse,
  widgetIds: string[],
): SonIAInsight {
  if (widgetIds.length === 0) {
    return {
      mood: 'curious',
      headline: 'Seu painel ainda está vazio.',
      detail:
        'Quando você escolher alguns widgets, eu vou olhar com calma e trazer observações sobre eles. Clique em "Personalizar painel" pra começar.',
    }
  }

  // Estratégia: 1 bullet de cada widget primeiro (garante diversidade — o user
  // vê algo sobre cada coisa que escolheu mostrar). Depois preenche com extras
  // até bater o target (= min(nro_widgets, 5)).
  const primary: Bullet[] = []
  const extras: Bullet[] = []
  for (const id of shuffle(widgetIds)) {
    const fn = BULLETS_BY_WIDGET[id]
    if (!fn) continue
    const widgetBullets = shuffle(fn(data))
    if (widgetBullets.length > 0) primary.push(widgetBullets[0])
    if (widgetBullets.length > 1) extras.push(...widgetBullets.slice(1))
  }

  if (primary.length === 0) {
    return {
      mood: 'happy',
      headline: 'Tudo tranquilo por aqui.',
      detail: 'Olhei os widgets que você escolheu e não achei nada urgente pra hoje.',
    }
  }

  // Target: 1 bullet por widget, mas cap em 5. Se sobrar slot, completa com extras.
  const target = Math.min(widgetIds.length, 5)
  const merged = [...primary, ...shuffle(extras)]
  const bullets = merged.slice(0, Math.min(target, merged.length))

  const hasNegative = bullets.some((b) => b.tone === 'negative')
  const hasWarning = bullets.some((b) => b.tone === 'warning')
  const mood: SonIAInsight['mood'] = hasNegative
    ? 'alert'
    : hasWarning
    ? 'curious'
    : 'happy'

  const headline =
    pick(hasNegative || hasWarning ? HEADLINES_ALERT : HEADLINES_NEUTRAL) ??
    'Trouxe algumas observações.'

  const detail =
    'Selecionei alguns pontos dos widgets que você escolheu — me chama se quiser que eu olhe alguma página específica.'

  return { mood, headline, detail, bullets }
}
