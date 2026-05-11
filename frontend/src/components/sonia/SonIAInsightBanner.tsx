import { ChevronRight, Sparkles } from 'lucide-react'
import SonIAAvatar, { type SonIAMood } from './SonIAAvatar'
import SonIABrand from './SonIABrand'
import type { HomeDashboardResponse } from '@/types/home'

interface SonIAInsightBannerProps {
  data: HomeDashboardResponse
  firstName: string
}

interface Insight {
  mood: SonIAMood
  headline: string
  detail: string
  ctaLabel?: string
  ctaHref?: string
  accent: string  // tailwind tint
}

const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtBRLshort = (n: number) =>
  Math.abs(n) >= 1_000_000
    ? `R$ ${(n / 1_000_000).toFixed(1)}M`
    : Math.abs(n) >= 1_000
    ? `R$ ${(n / 1_000).toFixed(0)}k`
    : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(n)

function pickInsight(data: HomeDashboardResponse, firstName: string): Insight {
  const nome = firstName || ''
  const oi = nome ? `Oi, ${nome}.` : 'Oi.'
  const inad = data.inadimplencia_critica
  const pend = data.pendencias
  const recall = data.recall
  const orc = data.orcamentos_parados
  const top = data.top_profs_semana

  // 1) ALERT — inadimplência crítica
  if (inad && inad.total >= 5) {
    return {
      mood: 'alert',
      headline: `${oi} Queria te mostrar uma coisa.`,
      detail: `Encontrei ${fmtNum(inad.total)} parcelas em aberto há bastante tempo, somando ${fmtBRLshort(inad.valor_total)}. Que tal a gente dar uma olhada com calma hoje?`,
      ctaLabel: 'Ver detalhes',
      ctaHref: '/financeiro',
      accent: 'from-rose-50 to-white border-rose-200',
    }
  }

  // 2) ALERT — pendências operacionais
  if (pend && pend.total >= 10) {
    return {
      mood: 'alert',
      headline: `${oi} Tenho uma observação pra te trazer.`,
      detail: `Notei ${fmtNum(pend.total)} pendências aguardando, organizadas em ${pend.buckets.length} tipos. Se quiser, podemos começar pelas mais urgentes — uma de cada vez.`,
      ctaLabel: 'Ver pendências',
      ctaHref: '/agenda',
      accent: 'from-amber-50 to-white border-amber-200',
    }
  }

  // 3) HAPPY — semana forte
  if (top && top.items.length > 0 && top.items[0].valor_aprovado >= 10_000) {
    const lider = top.items[0]
    const primeiroNome = lider.nome.split(/\s+/)[0]
    return {
      mood: 'happy',
      headline: `${oi} Olha que notícia boa.`,
      detail: `${primeiroNome} está fazendo uma semana muito especial — já são ${fmtBRLshort(lider.valor_aprovado)} em orçamentos aprovados. A equipe toda está com um ritmo bonito.`,
      ctaLabel: 'Ver a equipe',
      ctaHref: '/analise/comercial',
      accent: 'from-emerald-50 to-white border-emerald-200',
    }
  }

  // 4) CURIOUS — recall
  if (recall && recall.items.length >= 3) {
    return {
      mood: 'curious',
      headline: `${oi} Olha o que encontrei.`,
      detail: `Selecionei ${fmtNum(recall.items.length)} pacientes que vinham com frequência e estão um pouquinho atrasados. Uma ligação carinhosa costuma fazer diferença pra eles.`,
      ctaLabel: 'Ver pacientes',
      ctaHref: '/pacientes',
      accent: 'from-primary-50 to-white border-primary-200',
    }
  }

  // 5) CURIOUS — orçamentos parados
  if (orc && orc.total >= 3) {
    return {
      mood: 'curious',
      headline: `${oi} Tenho uma sugestão pra você.`,
      detail: `Reparei em ${fmtNum(orc.total)} orçamentos aprovados sem retorno há um tempinho — são ${fmtBRLshort(orc.valor_total)} esperando. Quem sabe um contato gentil retoma essas conversas?`,
      ctaLabel: 'Ver orçamentos',
      ctaHref: '/analise/comercial',
      accent: 'from-primary-50 to-white border-primary-200',
    }
  }

  // 6) DEFAULT — boas-vindas
  return {
    mood: 'default',
    headline: `${oi} Que bom te ver por aqui.`,
    detail: 'Vou te acompanhar no dia a dia e, conforme os dados chegarem, separo com carinho o que merece sua atenção primeiro. Pode contar comigo.',
    accent: 'from-primary-50 to-white border-primary-200',
  }
}

export default function SonIAInsightBanner({ data, firstName }: SonIAInsightBannerProps) {
  const insight = pickInsight(data, firstName)

  return (
    <div className={`bg-gradient-to-r ${insight.accent} border rounded-xl shadow-sm p-4 sm:p-5 flex items-center gap-4`}>
      <SonIAAvatar mood={insight.mood} size="xl" ring className="hidden sm:block" />
      <SonIAAvatar mood={insight.mood} size="lg" ring className="sm:hidden" />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <SonIABrand size="md" />
          <span className="text-[10px] uppercase tracking-wider font-bold text-neutral-500 bg-white border border-neutral-200 px-1.5 py-0.5 rounded">
            <Sparkles size={9} className="inline mb-0.5 mr-0.5" /> Heurístico
          </span>
        </div>
        <div className="text-sm sm:text-base font-semibold text-neutral-900 leading-tight">
          {insight.headline}
        </div>
        <div className="text-xs sm:text-sm text-neutral-700 mt-1 leading-snug">
          {insight.detail}
        </div>
      </div>

      {insight.ctaLabel && insight.ctaHref && (
        <a
          href={insight.ctaHref}
          className="hidden md:inline-flex items-center gap-1 text-sm font-semibold text-primary-700 hover:text-primary-900 transition shrink-0 whitespace-nowrap"
        >
          {insight.ctaLabel}
          <ChevronRight size={16} />
        </a>
      )}
    </div>
  )
}
