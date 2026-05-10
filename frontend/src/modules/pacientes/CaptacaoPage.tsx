/**
 * Captação & Origem (Frente A — HowDidMeet/IndicationSource).
 *
 * Foco estratégico: mostrar o GAP de preenchimento como choque visual,
 * forçando a conversa "treine sua recepção a perguntar como o paciente
 * conheceu a clínica" — habilita ROI por canal no futuro.
 *
 * Estrutura:
 * 1. Banner de choque (preenchimento global)
 * 2. Card "Como conheceu a clínica" — distribuição dos preenchidos
 * 3. Card "Indicações nominais" — top quem indicou (com nome)
 * 4. CTA "Treine sua recepção"
 */
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, BarChart3, ClipboardCheck, Globe, Hash, Loader2,
  MessageCircle, Search, TrendingUp, UserPlus, Users,
} from 'lucide-react'

import { usePageTitle } from '@/contexts/PageTitleContext'
import { analiseService } from '@/services/analise.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageFooter } from '@/components/layout/PageFooter'
import type {
  CaptacaoOrigemItem, CaptacaoOrigemResponse, IndicacaoNominal,
} from '@/types/analise'

// ── Helpers ───────────────────────────────────────────────────

const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)

const CANAL_META: Record<string, { color: string; bg: string; bar: string; icon: React.ReactNode }> = {
  Facebook:   { color: 'text-blue-700',    bg: 'bg-blue-50',    bar: 'bg-blue-500',    icon: <Globe size={14} /> },
  Instagram:  { color: 'text-pink-700',    bg: 'bg-pink-50',    bar: 'bg-pink-500',    icon: <Hash size={14} /> },
  Google:     { color: 'text-emerald-700', bg: 'bg-emerald-50', bar: 'bg-emerald-500', icon: <Search size={14} /> },
  Indicação:  { color: 'text-amber-700',   bg: 'bg-amber-50',   bar: 'bg-amber-500',   icon: <MessageCircle size={14} /> },
  Outros:     { color: 'text-neutral-600', bg: 'bg-neutral-100', bar: 'bg-neutral-400', icon: <Users size={14} /> },
}
const corCanal = (canal: string) => CANAL_META[canal] || {
  color: 'text-sky-700', bg: 'bg-sky-50', bar: 'bg-sky-500', icon: <Users size={14} />,
}

// ── Page ──────────────────────────────────────────────────────

export default function CaptacaoPage() {
  usePageTitle('Captação & Origem')

  const query = useQuery({
    queryKey: ['analise', 'captacao'],
    queryFn: () => analiseService.pacientesCaptacao(),
    staleTime: 60_000,
  })

  return (
    <PageContainer>
      <PageHeader
        eyebrow="PACIENTES"
        title="Captação & Origem"
        subtitle="De onde vêm seus pacientes — e quanto desse dado você está perdendo"
        icon={<UserPlus size={20} />}
      />
      {query.isLoading && (
        <div className="flex items-center justify-center py-12 text-neutral-500 gap-2">
          <Loader2 className="animate-spin" size={18} /> Carregando dados de captação...
        </div>
      )}
      {query.isError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-800 text-sm">
          Erro ao carregar dados. Tente novamente.
        </div>
      )}
      {query.data && <Body data={query.data} />}
      <PageFooter dataSource="Clinicorp" />
    </PageContainer>
  )
}

function Body({ data }: { data: CaptacaoOrigemResponse }) {
  return (
    <>
      <BannerChoque data={data} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <CanaisCard data={data.canais} totalPreenchido={data.total_com_origem} />
        <IndicacoesCard data={data.indicacoes_nominais} />
      </div>
      <TreineRecepcaoCard data={data} />
    </>
  )
}

// ── Banner de choque ──────────────────────────────────────────

function BannerChoque({ data }: { data: CaptacaoOrigemResponse }) {
  const semOrigem = data.total_consultas - data.total_com_origem
  const pctSem = 100 - data.pct_preenchimento
  return (
    <section className="bg-gradient-to-br from-rose-50 to-amber-50 border border-rose-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <AlertTriangle size={22} className="text-rose-600 shrink-0 mt-1" />
        <div className="flex-1">
          <div className="text-[10px] uppercase tracking-wider font-bold text-rose-700 mb-1">
            ⚡ você está perdendo dado de marketing
          </div>
          <h3 className="text-xl font-bold text-rose-900 leading-tight">
            <span className="tabular-nums">{pctSem.toFixed(1)}%</span> dos pacientes
            <span className="text-rose-700"> não têm origem registrada</span>
          </h3>
          <div className="mt-2 text-[13px] text-rose-800 leading-snug">
            De <strong className="tabular-nums">{fmtNum(data.total_consultas)}</strong> consultas,
            apenas <strong className="tabular-nums text-emerald-700">{fmtNum(data.total_com_origem)}</strong>
            {' '}têm o campo "como conheceu a clínica" preenchido
            ({data.pct_preenchimento.toFixed(2)}%).
            Outras <strong className="tabular-nums">{fmtNum(semOrigem)}</strong> consultas você
            não sabe se vieram do Instagram, do Google, de indicação ou da rua.
          </div>
          <div className="mt-3 flex items-center gap-2 text-[11.5px] text-rose-900/80">
            <TrendingUp size={13} className="text-rose-700 shrink-0" />
            <span>
              Sem esse dado, <strong>não dá pra calcular ROI por canal</strong> nem decidir onde
              colocar verba de mídia. Treinar a recepção a preencher é o primeiro passo.
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Card distribuição por canal ───────────────────────────────

function CanaisCard({
  data, totalPreenchido,
}: { data: CaptacaoOrigemItem[]; totalPreenchido: number }) {
  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 size={14} className="text-neutral-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Como conheceu a clínica
          </span>
        </div>
        <div className="text-sm text-neutral-400 py-6 text-center">
          Nenhum dado de origem registrado ainda.
        </div>
      </div>
    )
  }
  const max = Math.max(...data.map((c) => c.qtd_consultas), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Como conheceu a clínica
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(totalPreenchido)} consultas com origem registrada — distribuição abaixo
      </div>

      <ul className="space-y-2.5">
        {data.map((c) => {
          const meta = corCanal(c.canal)
          return (
            <li key={c.canal} className={`${meta.bg} rounded-md px-3 py-2`}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className={meta.color}>{meta.icon}</span>
                  <span className={`text-[12px] font-semibold ${meta.color}`}>{c.canal}</span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className={`text-[14px] font-bold tabular-nums ${meta.color}`}>
                    {fmtNum(c.qtd_consultas)}
                  </span>
                  <span className={`text-[11px] tabular-nums ${meta.color}`}>
                    {c.pct.toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-white rounded-full overflow-hidden">
                  <div
                    className={`h-full ${meta.bar} rounded-full`}
                    style={{ width: `${(c.qtd_consultas / max) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 tabular-nums w-20 text-right">
                  {c.qtd_pacientes} pacientes
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ── Card indicações nominais ──────────────────────────────────

function IndicacoesCard({ data }: { data: IndicacaoNominal[] }) {
  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <MessageCircle size={14} className="text-amber-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Quem indicou
          </span>
        </div>
        <div className="text-sm text-neutral-400 py-6 text-center">
          Nenhuma indicação nominal registrada.
        </div>
      </div>
    )
  }
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <MessageCircle size={14} className="text-amber-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Quem indicou — top {data.length}
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        Texto livre do campo "Indicado por" — descobre seus maiores promotores
      </div>
      <ul className="space-y-1.5">
        {data.map((i, idx) => (
          <li
            key={i.nome_indicador}
            className="flex items-center justify-between gap-2 px-3 py-2 bg-amber-50/50 rounded-md"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                {idx + 1}
              </span>
              <span className="text-[12px] font-medium text-neutral-800 truncate" title={i.nome_indicador}>
                {i.nome_indicador}
              </span>
            </div>
            <div className="flex items-center gap-3 shrink-0 text-[11px]">
              <span className="text-amber-700 font-bold tabular-nums">
                {i.qtd_consultas} {i.qtd_consultas === 1 ? 'consulta' : 'consultas'}
              </span>
              <span className="text-neutral-500 tabular-nums">
                {i.qtd_pacientes} {i.qtd_pacientes === 1 ? 'paciente' : 'pacientes'}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── CTA treine sua recepção ───────────────────────────────────

function TreineRecepcaoCard({ data }: { data: CaptacaoOrigemResponse }) {
  // Estimativa de "ganho potencial" se preenchimento subir pra 50%
  const meta50 = Math.round(data.total_consultas * 0.5)
  const ganho = meta50 - data.total_com_origem
  return (
    <section className="bg-gradient-to-br from-emerald-50 to-sky-50 border border-emerald-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <ClipboardCheck size={16} className="text-emerald-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-emerald-700">
          Como destravar ROI por canal
        </span>
      </div>
      <h3 className="text-base font-bold text-emerald-900 mb-2">
        Treine a recepção a perguntar "como conheceu a clínica?"
      </h3>
      <ul className="text-[12.5px] text-emerald-900 space-y-1.5 leading-snug">
        <li>✅ Pergunta padronizada no primeiro contato (telefone, WhatsApp, agendamento)</li>
        <li>✅ Campo obrigatório no Clinicorp (HowDidMeet) — não deixar passar</li>
        <li>✅ Para "indicação", anotar nome de quem indicou (IndicationSource)</li>
        <li>✅ Revisão semanal: meta de 50% de preenchimento nos novos cadastros</li>
      </ul>
      <div className="mt-3 pt-3 border-t border-emerald-200 text-[11.5px] text-emerald-800 leading-snug">
        <strong>Meta sugerida:</strong> chegar em <strong className="text-emerald-700">50% de preenchimento</strong>
        {' '}({fmtNum(meta50)} consultas) destravaria análise de ROI por canal — hoje precisaria de
        mais <strong className="tabular-nums">{fmtNum(ganho)}</strong> registros pra gente parar de chutar
        onde colocar verba de mídia.
      </div>
    </section>
  )
}
