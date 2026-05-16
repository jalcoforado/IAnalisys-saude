/**
 * Inteligência de Pacientes — agrega 6 visões analíticas:
 * 1. Acurácia preditiva (backtest)
 * 2. Top faltosos
 * 3. Curva de retenção
 * 4. Risco de evasão
 * 5. Heatmap no-show (dow × hora)
 * 6. Eficácia da confirmação
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, Brain, CalendarX, Clock, Loader2, Target,
  TrendingDown, TrendingUp, Users,
} from 'lucide-react'

import { usePageTitle } from '@/contexts/PageTitleContext'
import { analiseService } from '@/services/analise.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageFooter } from '@/components/layout/PageFooter'
import type {
  AcuraciaSection, EficaciaConfirmacao, EvasaoPaciente, HeatmapSection,
  RetencaoSection, TopFaltosoItem,
} from '@/types/pacientes-inteligencia'

// ── Helpers ────────────────────────────────────────────────────

const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtPct = (n: number) => `${n}%`
const fmtDate = (s: string) => {
  const d = new Date(s + 'T12:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}
const safePct = (n: number, d: number) => (d > 0 ? Math.round((n / d) * 100) : 0)

const BUCKET_META: Record<'alto' | 'medio' | 'baixo', { label: string; color: string; bg: string; border: string }> = {
  alto:  { label: 'Alto risco',  color: 'text-error-text',   bg: 'bg-error-bg',   border: 'border-error-border' },
  medio: { label: 'Médio risco', color: 'text-warning-text', bg: 'bg-warning-bg', border: 'border-warning-border' },
  baixo: { label: 'Baixo risco', color: 'text-success-text', bg: 'bg-success-bg', border: 'border-success-border' },
}

const DOW_LABEL = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

// ── Página ─────────────────────────────────────────────────────

export default function InteligenciaPage() {
  usePageTitle('Inteligência de Pacientes')
  const [days, setDays] = useState(90)

  const query = useQuery({
    queryKey: ['analise', 'pacientes', 'inteligencia', days],
    queryFn: () => analiseService.pacientesInteligencia(days),
    staleTime: 60_000,
  })

  return (
    <PageContainer>
      <PageHeader
        eyebrow="PACIENTES"
        title="Inteligência"
        subtitle="6 visões para entender o comportamento dos pacientes da clínica: o quanto a previsão de falta acerta, quem mais falta, se os pacientes voltam, quem está sumido, em que dia/hora as faltas acontecem e se o lembrete ajuda."
        icon={<Brain size={20} />}
        actions={<PeriodoSwitcher value={days} onChange={setDays} />}
      />

      {query.isLoading && (
        <div className="flex items-center justify-center py-12 text-neutral-500 gap-2">
          <Loader2 className="animate-spin" size={18} /> Carregando inteligência...
        </div>
      )}

      {query.isError && (
        <div className="bg-error-bg border border-error-border text-error-text rounded-lg p-4 text-sm">
          Erro ao carregar. Tente recarregar a página.
        </div>
      )}

      {query.data && (
        <div className="space-y-6">
          <AcuraciaCard data={query.data.acuracia} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <RetencaoCard data={query.data.retencao} />
            <EficaciaCard data={query.data.eficacia_confirmacao} />
          </div>
          <HeatmapCard data={query.data.heatmap} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TopFaltososCard data={query.data.top_faltosos} />
            <EvasaoCard data={query.data.evasao_risco} />
          </div>
        </div>
      )}

      <PageFooter />
    </PageContainer>
  )
}

// ── Seletor de período ─────────────────────────────────────────

function PeriodoSwitcher({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const opcoes = [30, 60, 90, 180]
  return (
    <div className="flex items-center gap-1 bg-neutral-100 rounded-lg p-1">
      {opcoes.map((d) => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className={`px-3 py-1 text-xs font-medium rounded-md transition ${
            value === d
              ? 'bg-white text-primary-700 shadow-sm'
              : 'text-neutral-600 hover:text-neutral-900'
          }`}
        >
          {d}d
        </button>
      ))}
    </div>
  )
}

// ── 1. Acurácia preditiva ──────────────────────────────────────

function AcuraciaCard({ data }: { data: AcuraciaSection }) {
  if (data.appointments_avaliados === 0) {
    return (
      <Card title="Acurácia da Previsão" icon={<Target size={16} />}>
        <p className="text-sm text-neutral-500">Sem appointments finalizados no período pra avaliar.</p>
      </Card>
    )
  }

  return (
    <Card
      title="Acurácia da Previsão de No-Show"
      subtitle={`O sistema classifica cada paciente como alto, médio ou baixo risco de faltar. Aqui medimos o quanto ele acerta — recalculando a previsão para ${fmtNum(data.appointments_avaliados)} compromissos já finalizados, usando só dados anteriores ao dia de cada um.`}
      icon={<Target size={16} />}
    >
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KPI
          label="Acerto geral"
          value={fmtPct(data.acuracia_pct)}
          hint={`A cada 100 previsões, ${data.acuracia_pct} estão corretas (alto que faltou + baixo/médio que veio).`}
          tone="primary"
        />
        <KPI
          label="Quando alertamos, é falta?"
          value={fmtPct(data.precisao_alto_pct)}
          hint={`Dos pacientes marcados como ALTO risco, ${data.precisao_alto_pct}% realmente faltaram. Mede o quanto o alerta vermelho é confiável.`}
          tone="warning"
        />
        <KPI
          label="Capturamos as faltas?"
          value={fmtPct(data.recall_alto_pct)}
          hint={`Das faltas que aconteceram de fato, ${data.recall_alto_pct}% tinham sido marcadas como ALTO risco antes. Mede o quanto pegamos as faltas reais.`}
          tone="error"
        />
        <KPI
          label="Falta natural da clínica"
          value={fmtPct(data.baseline_pct)}
          hint={`Sem usar nenhuma previsão, ${data.baseline_pct}% dos compromissos viram falta. É a régua para comparar.`}
          tone="neutral"
        />
      </div>

      {/* Buckets */}
      <div className="mb-2 text-xs text-neutral-600">
        <strong className="text-neutral-800">Como o sistema separa os pacientes:</strong> de cada faixa, qual % de fato faltou.
        Idealmente, "Alto risco" deveria ter taxa muito maior que "Baixo risco" — é assim que sabemos que a previsão funciona.
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
        {data.buckets.map((b) => {
          const meta = BUCKET_META[b.bucket]
          return (
            <div key={b.bucket} className={`${meta.bg} ${meta.border} border rounded-lg p-3`}>
              <div className={`text-xs font-semibold uppercase ${meta.color}`}>{meta.label}</div>
              <div className="text-2xl font-bold text-neutral-900 mt-1">{fmtPct(b.taxa_falta_pct)}</div>
              <div className="text-xs text-neutral-600 mt-1">
                {fmtNum(b.faltou)} de {fmtNum(b.total)} pacientes desta faixa faltaram
              </div>
            </div>
          )
        })}
      </div>

      {/* Matriz de confusão visual */}
      <div className="mb-2 text-xs text-neutral-600">
        <strong className="text-neutral-800">Comparação previsão × realidade:</strong> cada quadrante mostra
        quantos compromissos caíram em cada combinação. Quanto mais números nos cantos verdes
        (alto que faltou e baixo que veio), melhor o sistema está prevendo.
      </div>
      <div className="border border-neutral-200 rounded-lg overflow-hidden">
        <div className="grid grid-cols-4 text-xs">
          <div className="px-3 py-2 bg-neutral-50 font-semibold text-neutral-600">O que aconteceu ↓ / O que previmos →</div>
          <div className="px-3 py-2 bg-neutral-50 font-semibold text-neutral-700 text-center">Alto</div>
          <div className="px-3 py-2 bg-neutral-50 font-semibold text-neutral-700 text-center">Médio</div>
          <div className="px-3 py-2 bg-neutral-50 font-semibold text-neutral-700 text-center">Baixo</div>

          <div className="px-3 py-2 bg-neutral-50 font-semibold text-error-text border-t">Faltou</div>
          <div className="px-3 py-2 text-center font-mono text-success-text bg-success-bg/50 border-t" title="Acerto: previmos alto e o paciente faltou">{fmtNum(data.matriz[0][0])}</div>
          <div className="px-3 py-2 text-center font-mono text-neutral-700 border-t" title="Previmos médio mas o paciente faltou">{fmtNum(data.matriz[0][1])}</div>
          <div className="px-3 py-2 text-center font-mono text-error-text bg-error-bg/50 border-t" title="Erro grave: previmos baixo mas o paciente faltou (escape)">{fmtNum(data.matriz[0][2])}</div>

          <div className="px-3 py-2 bg-neutral-50 font-semibold text-neutral-700 border-t">Veio</div>
          <div className="px-3 py-2 text-center font-mono text-warning-text bg-warning-bg/50 border-t" title="Alarme falso: previmos alto mas o paciente veio">{fmtNum(data.matriz[1][0])}</div>
          <div className="px-3 py-2 text-center font-mono text-neutral-700 border-t" title="Previmos médio e o paciente veio">{fmtNum(data.matriz[1][1])}</div>
          <div className="px-3 py-2 text-center font-mono text-success-text bg-success-bg/50 border-t" title="Acerto: previmos baixo e o paciente veio">{fmtNum(data.matriz[1][2])}</div>
        </div>
        <div className="px-3 py-2 bg-neutral-50 text-[11px] text-neutral-500 border-t border-neutral-200">
          <span className="inline-block px-1 bg-success-bg/50 rounded mr-1">Verde</span>= sistema acertou ·
          <span className="inline-block px-1 bg-error-bg/50 rounded mx-1">Vermelho</span>= falta que passou batido ·
          <span className="inline-block px-1 bg-warning-bg/50 rounded mx-1">Amarelo</span>= alarme falso (alertamos e o paciente veio)
        </div>
      </div>

      {/* Listas paralelas: acertos vs escapes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">
        <SubList
          title="Pacientes que avisamos e faltaram"
          subtitle={`${fmtNum(data.acertos_alto_risco.length)} casos em que marcamos alto risco e o paciente realmente faltou — o sistema funcionou.`}
          tone="success"
          items={data.acertos_alto_risco}
          empty="Nenhum acerto de alto risco no período."
        />
        <SubList
          title="Faltas que não previmos"
          subtitle={`${fmtNum(data.escapes.length)} casos em que o paciente faltou mas o sistema marcou como baixo ou médio risco — o que precisamos melhorar.`}
          tone="error"
          items={data.escapes}
          empty="Nenhuma falta passou batido — todas foram previstas como alto risco."
        />
      </div>
    </Card>
  )
}

function SubList({
  title, subtitle, tone, items, empty,
}: {
  title: string
  subtitle: string
  tone: 'success' | 'error'
  items: { paciente_nome: string; data: string; risco_pct: number; bucket: 'alto' | 'medio' | 'baixo'; razao: string }[]
  empty: string
}) {
  const toneClass = tone === 'success' ? 'text-success-text' : 'text-error-text'
  return (
    <div className="border border-neutral-200 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-neutral-50 border-b border-neutral-200">
        <div className={`text-xs font-semibold ${toneClass}`}>{title}</div>
        <div className="text-[11px] text-neutral-500">{subtitle}</div>
      </div>
      {items.length === 0 ? (
        <div className="px-3 py-4 text-xs text-neutral-500">{empty}</div>
      ) : (
        <ul className="divide-y divide-neutral-100 max-h-72 overflow-y-auto">
          {items.slice(0, 12).map((p, i) => {
            const meta = BUCKET_META[p.bucket]
            return (
              <li key={`${p.paciente_nome}-${i}`} className="px-3 py-2 flex items-center gap-2 text-xs">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-neutral-800 truncate">{p.paciente_nome}</div>
                  <div className="text-[11px] text-neutral-500">{fmtDate(p.data)} · {p.razao}</div>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${meta.bg} ${meta.color}`}>
                  {p.risco_pct}%
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ── 2. Top faltosos ────────────────────────────────────────────

function TopFaltososCard({ data }: { data: TopFaltosoItem[] }) {
  return (
    <Card
      title="Quem mais falta no período"
      subtitle="Ranking dos 20 pacientes com mais faltas. A taxa ao lado é a falta pessoal (faltou ÷ marcados). Útil pra ligar antes ou pedir confirmação reforçada na próxima."
      icon={<CalendarX size={16} />}
    >
      {data.length === 0 ? (
        <p className="text-sm text-neutral-500">Nenhuma falta registrada no período.</p>
      ) : (
        <ul className="divide-y divide-neutral-100">
          {data.map((p) => (
            <li key={p.paciente_external_id} className="py-2 flex items-center gap-3 text-sm">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-neutral-800 truncate">{p.paciente_nome}</div>
                <div className="text-xs text-neutral-500">
                  {p.faltas} faltas · {p.atendimentos} atendimentos · {p.total} marcados
                </div>
              </div>
              <span className="text-error-text font-bold">{p.faltas}×</span>
              <span className="text-xs text-neutral-500 w-12 text-right">{fmtPct(p.taxa_falta_pct)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

// ── 3. Curva de retenção ───────────────────────────────────────

function RetencaoCard({ data }: { data: RetencaoSection }) {
  const max = Math.max(...data.buckets.map((b) => b.taxa_pct), 1)
  return (
    <Card
      title="Os pacientes voltam?"
      subtitle="De cada 100 pacientes que vieram pela 1ª vez, quantos voltaram em até 30, 60, 90, 180 e 365 dias. Se a taxa de 30d cai, é sinal que a clínica está perdendo paciente novo logo no início."
      icon={<TrendingUp size={16} />}
    >
      <div className="space-y-3">
        {data.buckets.map((b) => (
          <div key={b.janela_dias}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-neutral-700 font-medium">Voltaram em até {b.janela_dias} dias</span>
              <span className="text-neutral-500">
                <strong className="text-neutral-800">{fmtPct(b.taxa_pct)}</strong> · {fmtNum(b.retornaram)} de {fmtNum(b.elegiveis)} pacientes
              </span>
            </div>
            <div className="w-full h-2 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-primary-500 to-primary-700 rounded-full transition-all"
                style={{ width: `${(b.taxa_pct / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-[11px] text-neutral-500">
        Conta apenas pacientes cuja 1ª visita foi há tempo suficiente pra caber na janela
        (ex: pra 90d, só pacientes cuja 1ª veio há 90+ dias).
      </div>
    </Card>
  )
}

// ── 4. Risco de evasão ─────────────────────────────────────────

function EvasaoCard({ data }: { data: EvasaoPaciente[] }) {
  return (
    <Card
      title="Pacientes ativos que sumiram"
      subtitle="Pacientes que vieram pelo menos 3 vezes nos últimos 12 meses (eram fiéis) mas não voltam há mais de 90 dias. Lista os 30 mais antigos sem voltar — bons candidatos para uma ligação de reativação."
      icon={<Users size={16} />}
    >
      {data.length === 0 ? (
        <p className="text-sm text-neutral-500">Nenhum paciente ativo sumido.</p>
      ) : (
        <ul className="divide-y divide-neutral-100 max-h-80 overflow-y-auto">
          {data.map((p) => (
            <li key={p.paciente_external_id} className="py-2 flex items-center gap-3 text-sm">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-neutral-800 truncate">{p.paciente_nome}</div>
                <div className="text-xs text-neutral-500">
                  {p.visitas_12m} visitas em 12m · última {fmtDate(p.ultima_visita)}
                </div>
              </div>
              <span className="text-xs font-semibold text-warning-text bg-warning-bg px-2 py-0.5 rounded">
                {p.dias_sem_voltar}d
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

// ── 5. Heatmap no-show ─────────────────────────────────────────

function HeatmapCard({ data }: { data: HeatmapSection }) {
  // Determinar amplitude horária dos dados pra grade enxuta
  const horas = Array.from(new Set(data.celulas.map((c) => c.hora))).sort((a, b) => a - b)
  const minH = horas[0] ?? 8
  const maxH = horas[horas.length - 1] ?? 19
  const horasFaixa = Array.from({ length: maxH - minH + 1 }, (_, i) => minH + i)

  // Mapa (dow, hora) → célula
  const mapa = new Map<string, typeof data.celulas[number]>()
  for (const c of data.celulas) mapa.set(`${c.dow}-${c.hora}`, c)

  const taxaMax = Math.max(...data.celulas.map((c) => c.taxa_falta_pct), 1)

  const bgFor = (pct: number, total: number) => {
    if (total === 0) return 'bg-neutral-50'
    const intensity = pct / taxaMax
    if (intensity > 0.75) return 'bg-error-text text-white'
    if (intensity > 0.5)  return 'bg-error-bg text-error-text'
    if (intensity > 0.25) return 'bg-warning-bg text-warning-text'
    if (intensity > 0)    return 'bg-success-bg text-success-text'
    return 'bg-neutral-50 text-neutral-400'
  }

  const taxaGlobal = safePct(data.faltas_global, data.total_global)
  return (
    <Card
      title="Quando as faltas acontecem"
      subtitle={`Mostra a % de falta em cada dia da semana × horário. Quanto mais escura a célula, maior a chance de o paciente não aparecer naquele horário. No total: ${fmtNum(data.faltas_global)} faltas em ${fmtNum(data.total_global)} compromissos (${taxaGlobal}%).`}
      icon={<Clock size={16} />}
    >
      <div className="overflow-x-auto">
        <table className="text-[11px]">
          <thead>
            <tr>
              <th className="text-left py-1 pr-2 text-neutral-500 font-medium"></th>
              {horasFaixa.map((h) => (
                <th key={h} className="px-1 py-1 text-center text-neutral-500 font-medium w-9">{h}h</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DOW_LABEL.map((label, dow) => (
              <tr key={dow}>
                <td className="py-1 pr-2 text-neutral-600 font-medium">{label}</td>
                {horasFaixa.map((h) => {
                  const c = mapa.get(`${dow}-${h}`)
                  const total = c?.total ?? 0
                  const pct = c?.taxa_falta_pct ?? 0
                  return (
                    <td
                      key={h}
                      className={`px-1 py-1 text-center rounded ${bgFor(pct, total)}`}
                      title={c
                        ? `${label} ${h}h: ${c.faltas} de ${total} pacientes faltaram (${pct}%)`
                        : `${label} ${h}h: sem compromissos no período`}
                    >
                      {total > 0 ? `${pct}%` : '·'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 text-[11px] text-neutral-500 flex items-center gap-3 flex-wrap">
        <span><strong>% de falta:</strong></span>
        <span className="px-2 py-0.5 bg-neutral-50 rounded">sem dados</span>
        <span className="px-2 py-0.5 bg-success-bg rounded">baixa</span>
        <span className="px-2 py-0.5 bg-warning-bg rounded">média</span>
        <span className="px-2 py-0.5 bg-error-bg rounded">alta</span>
        <span className="px-2 py-0.5 bg-error-text text-white rounded">crítica</span>
        <span className="text-neutral-400">· passe o mouse sobre uma célula para ver os números</span>
      </div>
    </Card>
  )
}

// ── 6. Eficácia da confirmação ─────────────────────────────────

function EficaciaCard({ data }: { data: EficaciaConfirmacao }) {
  const amostraInsuficiente = data.com_lembrete_total < 50
  const reduzFalta = data.diferenca_pp > 0
  const aumentaFalta = data.diferenca_pp < 0
  const diff = Math.abs(data.diferenca_pp)

  return (
    <Card
      title="O lembrete está funcionando?"
      subtitle="Compara a taxa de falta entre os pacientes que receberam lembrete (campo has_lembrete marcado) e os que não receberam. A ideia é confirmar se o esforço do lembrete vale a pena."
      icon={<AlertTriangle size={16} />}
    >
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-3">
          <div className="text-xs font-semibold uppercase text-primary-700">Com lembrete</div>
          <div className="text-2xl font-bold text-neutral-900 mt-1">{fmtPct(data.com_lembrete_taxa_pct)} faltam</div>
          <div className="text-xs text-neutral-600 mt-1">
            {fmtNum(data.com_lembrete_faltas)} faltas em {fmtNum(data.com_lembrete_total)} compromissos
          </div>
        </div>
        <div className="bg-neutral-50 border border-neutral-200 rounded-lg p-3">
          <div className="text-xs font-semibold uppercase text-neutral-700">Sem lembrete</div>
          <div className="text-2xl font-bold text-neutral-900 mt-1">{fmtPct(data.sem_lembrete_taxa_pct)} faltam</div>
          <div className="text-xs text-neutral-600 mt-1">
            {fmtNum(data.sem_lembrete_faltas)} faltas em {fmtNum(data.sem_lembrete_total)} compromissos
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-sm bg-neutral-50 border border-neutral-200 rounded-lg p-3">
        {reduzFalta ? (
          <>
            <TrendingDown size={18} className="text-success-text shrink-0" />
            <span className="text-neutral-700">
              Quem recebe lembrete falta <strong className="text-success-text">{diff}%</strong> a menos.
              O lembrete está ajudando.
            </span>
          </>
        ) : aumentaFalta ? (
          <>
            <TrendingUp size={18} className="text-error-text shrink-0" />
            <span className="text-neutral-700">
              Quem recebe lembrete falta <strong className="text-error-text">{diff}%</strong> a mais.
              O resultado é estranho — pode ser que a clínica só marque "lembrete" quando o paciente é problemático.
            </span>
          </>
        ) : (
          <span className="text-neutral-700">Sem diferença significativa entre os dois grupos.</span>
        )}
      </div>

      <div className="mt-2 text-[11px] text-neutral-500">
        <strong>Cobertura:</strong> {fmtPct(data.cobertura_lembrete_pct)} dos compromissos
        ({fmtNum(data.com_lembrete_total)} de {fmtNum(data.com_lembrete_total + data.sem_lembrete_total)})
        têm o lembrete marcado.
      </div>

      {amostraInsuficiente && (
        <div className="mt-3 text-[11px] text-warning-text bg-warning-bg border border-warning-border rounded p-2">
          ⚠ Apenas {fmtNum(data.com_lembrete_total)} compromissos com lembrete — amostra pequena demais
          para concluir. Vale checar com a clínica se o campo "lembrete" está sendo usado de fato pra essa finalidade.
        </div>
      )}
    </Card>
  )
}

// ── Componentes auxiliares ─────────────────────────────────────

function Card({
  title, subtitle, icon, children,
}: {
  title: string; subtitle?: string; icon?: React.ReactNode; children: React.ReactNode
}) {
  return (
    <section className="bg-white border border-neutral-200 rounded-xl p-5 shadow-sm">
      <header className="flex items-start gap-2 mb-4">
        {icon && <span className="text-primary-700 mt-0.5">{icon}</span>}
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-bold text-neutral-900 uppercase tracking-wide">{title}</h2>
          {subtitle && <p className="text-xs text-neutral-500 mt-0.5">{subtitle}</p>}
        </div>
      </header>
      {children}
    </section>
  )
}

function KPI({
  label, value, hint, tone,
}: {
  label: string; value: string; hint?: string; tone: 'primary' | 'warning' | 'error' | 'neutral'
}) {
  const toneClass = {
    primary: 'text-primary-700',
    warning: 'text-warning-text',
    error:   'text-error-text',
    neutral: 'text-neutral-700',
  }[tone]
  return (
    <div className="bg-neutral-50 border border-neutral-200 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wide text-neutral-500 font-semibold">{label}</div>
      <div className={`text-2xl font-bold ${toneClass} mt-1`}>{value}</div>
      {hint && <div className="text-[10px] text-neutral-500 mt-1 leading-tight">{hint}</div>}
    </div>
  )
}
