/**
 * Custo de Adquirência — taxas de maquininha/boleto por forma de pagamento.
 *
 * Mostra 3 níveis de informação:
 * 1. Header: total das taxas + taxa EFETIVA (sobre base com taxa) + variação MoM/YoY
 * 2. Tabela por forma: bruto/líquido/taxa/taxa% pra cada forma
 * 3. Insight: economia potencial anual se 30% do crédito virasse Pix
 *
 * Por que "taxa efetiva" e não "taxa global"?
 *   Global = taxas / bruto_total (mascarado por Pix/Dinheiro/Transferência)
 *   Efetiva = taxas / bruto_com_taxa (mostra o custo REAL da maquininha)
 */
import { useState } from 'react'
import { ChevronDown, CreditCard, Info, Lightbulb, Percent, TrendingDown, TrendingUp } from 'lucide-react'

import type { TaxaPorForma, TaxasSection } from '@/types/analise'

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
  if (compact && Math.abs(n) >= 1_000) return `R$ ${(n / 1_000).toFixed(0)}k`
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
  }).format(n)
}

const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)

// Mapa de cor por faixa de taxa%. Verde = sem taxa, rosa = caro.
function colorFor(taxaPct: number): { bar: string; bg: string; text: string; border: string } {
  if (taxaPct === 0) return { bar: 'bg-emerald-500', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' }
  if (taxaPct < 1)   return { bar: 'bg-lime-500',    bg: 'bg-lime-50',    text: 'text-lime-700',    border: 'border-lime-200' }
  if (taxaPct < 2)   return { bar: 'bg-amber-500',   bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200' }
  if (taxaPct < 3)   return { bar: 'bg-orange-500',  bg: 'bg-orange-50',  text: 'text-orange-700',  border: 'border-orange-200' }
  return { bar: 'bg-rose-500', bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' }
}

// Ícone/label sucinto por forma — ajuda o dono identificar rápido.
function iconFor(forma: string): string {
  if (forma.includes('Crédito')) return '💳'
  if (forma.includes('Débito'))  return '💳'
  if (forma === 'Pix')           return '⚡'
  if (forma === 'Boleto')        return '📄'
  if (forma === 'Dinheiro')      return '💵'
  if (forma === 'Transferência') return '🏦'
  return '💰'
}

export function CustoAdquirenciaCard({ data }: { data: TaxasSection }) {
  if (data.bruto_total === 0) {
    return (
      <section className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm text-sm text-neutral-500">
        Sem pagamentos recebidos no período pra calcular taxas.
      </section>
    )
  }

  const fmtPP = (pp: number | null) => {
    if (pp === null || pp === undefined) return null
    const sign = pp > 0 ? '+' : ''
    // Pra "taxa efetiva", subir = ruim, cair = bom
    const cls = pp > 0.05 ? 'text-rose-600' : pp < -0.05 ? 'text-emerald-600' : 'text-neutral-500'
    const icon = pp > 0.05 ? <TrendingUp size={11} /> : pp < -0.05 ? <TrendingDown size={11} /> : null
    return { txt: `${sign}${pp.toFixed(2)}pp`, cls, icon }
  }
  const mom = fmtPP(data.mom_efetiva_pct)
  const yoy = fmtPP(data.yoy_efetiva_pct)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <header className="px-5 py-4 border-b border-neutral-100 flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-rose-50 ring-1 ring-rose-100 flex items-center justify-center text-rose-600 shrink-0">
            <CreditCard size={18} />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
              Custo de adquirência
            </div>
            <div className="text-sm text-neutral-700 mt-0.5">
              <strong className="text-rose-600 tabular-nums">{fmtBRL(data.taxas_total)}</strong> em taxas neste mês
            </div>
          </div>
        </div>

        <div className="flex items-baseline gap-6 shrink-0">
          {/* Taxa EFETIVA — destaque */}
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-neutral-500 flex items-center gap-1 justify-end">
              <Percent size={10} /> Taxa efetiva
            </div>
            <div className="text-2xl font-bold text-rose-600 tabular-nums leading-tight">
              {data.taxa_efetiva_pct.toFixed(2)}%
            </div>
            <div className="text-[10px] text-neutral-500">
              sobre {fmtBRL(data.bruto_com_taxa, true)} (cartão+boleto)
            </div>
          </div>
          {/* Taxa global — secundário */}
          <div className="text-right opacity-70">
            <div className="text-[10px] uppercase tracking-wider text-neutral-500">Global</div>
            <div className="text-base font-semibold text-neutral-700 tabular-nums">
              {data.taxa_global_pct.toFixed(2)}%
            </div>
            <div className="text-[10px] text-neutral-400">
              sobre {fmtBRL(data.bruto_total, true)} total
            </div>
          </div>
          {/* MoM/YoY */}
          {(mom || yoy) && (
            <div className="text-[11px] tabular-nums">
              {mom && <div className={`${mom.cls} flex items-center gap-1 justify-end`}>{mom.icon}<span>MoM {mom.txt}</span></div>}
              {yoy && <div className={`${yoy.cls} flex items-center gap-1 justify-end mt-0.5`}>{yoy.icon}<span>YoY {yoy.txt}</span></div>}
            </div>
          )}
        </div>
      </header>

      {/* Tabela por forma */}
      <div className="px-5 py-3">
        <div className="text-[10px] uppercase tracking-wider text-neutral-500 font-semibold mb-2">
          Detalhamento por forma de pagamento
        </div>
        <div className="grid grid-cols-1 gap-1.5">
          {data.por_forma.map((f) => (
            <FormaRow key={f.forma_pagamento} f={f} />
          ))}
        </div>
      </div>

      {/* Insight: economia potencial */}
      {data.economia_potencial_anual > 0 && (
        <div className="px-5 py-3 border-t border-neutral-100 bg-emerald-50/40 flex items-start gap-3">
          <Lightbulb size={16} className="text-emerald-600 shrink-0 mt-0.5" />
          <div className="text-[12px] text-neutral-700">
            <strong className="text-emerald-700">Economia potencial:</strong>{' '}
            migrando 30% do volume de Cartão de Crédito para Pix/Dinheiro,
            a clínica economizaria{' '}
            <strong className="text-emerald-700 tabular-nums">{fmtBRL(data.economia_potencial_anual)}</strong>{' '}
            em taxas no próximo ano (estimativa baseada na taxa efetiva atual).
          </div>
        </div>
      )}

      {/* Nota de metodologia — sempre visível, expansível pra detalhes */}
      <MetodologiaNota isEstimated={data.is_estimated} />
    </section>
  )
}

// ── Nota de metodologia (transparência sobre como a taxa é calculada) ─

function MetodologiaNota({ isEstimated }: { isEstimated: boolean }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="border-t border-neutral-100 bg-neutral-50/40">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-2.5 flex items-center justify-between gap-3 text-left hover:bg-neutral-50 transition"
      >
        <div className="flex items-center gap-2 text-[11px] text-neutral-600">
          <Info size={13} className={isEstimated ? 'text-amber-600' : 'text-emerald-600'} />
          <span>
            {isEstimated ? (
              <>
                Taxa por forma é <strong className="text-amber-700">estimada</strong>{' '}
                <span className="text-neutral-500">(API Clinicorp não expõe valor exato por forma)</span>
              </>
            ) : (
              <>
                Taxa por forma <strong className="text-emerald-700">exata</strong> (vinda direto da API)
              </>
            )}
          </span>
        </div>
        <ChevronDown
          size={14}
          className={`text-neutral-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {expanded && (
        <div className="px-5 pb-4 text-[11.5px] text-neutral-700 space-y-2 leading-relaxed">
          <div className="font-semibold text-neutral-800 text-[12px]">Como o cálculo é feito</div>

          <div>
            <strong className="text-neutral-800">Totais (exatos):</strong>
            <ul className="list-disc list-inside ml-1 mt-0.5 space-y-0.5 text-neutral-600">
              <li>
                <strong>Bruto</strong> = SUM(<code className="font-mono text-[10.5px]">core_payments.amount</code>)
                onde <code className="font-mono text-[10.5px]">is_received=1</code>, mês de{' '}
                <code className="font-mono text-[10.5px]">received_date</code> — bate com "Valor Total" do PDF
                "Pagamentos e Comissões" do Clinicorp
              </li>
              <li>
                <strong>Líquido</strong> = SUM(<code className="font-mono text-[10.5px]">core_summary_entries.amount</code>)
                onde <code className="font-mono text-[10.5px]">type='DEBIT' AND post_type='RECEIVED'</code> —
                bate com "Valor" do PDF
              </li>
              <li>
                <strong>Taxa total</strong> = Bruto − Líquido — bate com "Taxas/Descontos" do PDF
              </li>
            </ul>
          </div>

          <div>
            <strong className="text-neutral-800">Fatiamento por forma:</strong>
            <p className="text-neutral-600 mt-0.5">
              A API REST do Clinicorp <strong>não expõe</strong> a taxa por forma de pagamento
              individualmente — esse dado existe apenas no relatório interno da UI. Pra estimar a
              distribuição, aplicamos taxas de mercado típicas em odontologia:
            </p>
            <ul className="list-none mt-1.5 ml-1 space-y-0.5 text-neutral-600">
              <li>• Cartão de Crédito: <strong>5,0%</strong></li>
              <li>• Cartão de Débito: <strong>0,9%</strong></li>
              <li>• Boleto: <strong>0,4%</strong></li>
              <li>• Pix, Dinheiro, Transferência: <strong>0%</strong></li>
            </ul>
            <p className="text-neutral-600 mt-1.5">
              Essas taxas são <strong>escaladas proporcionalmente</strong> pra somar exatamente o
              total real de taxas do mês. Resultado: erro &lt; 0,5pp por forma (validado contra o
              relatório real do Clinicorp em abr/2026).
            </p>
          </div>

          <div className="pt-1 border-t border-neutral-200/80">
            <strong className="text-neutral-800">Fonte dos dados:</strong>{' '}
            <span className="text-neutral-600">
              Sincronizado da API Clinicorp via <code className="font-mono text-[10.5px]">/payment/list</code>{' '}
              + <code className="font-mono text-[10.5px]">/financial/list_summary</code>. Atualizado a
              cada sincronização do tenant.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function FormaRow({ f }: { f: TaxaPorForma }) {
  const c = colorFor(f.taxa_pct)
  const semTaxa = f.taxa === 0
  return (
    <div className={`${c.bg} rounded-md border ${c.border} px-3 py-2.5`}>
      <div className="flex items-center gap-3">
        <div className={`w-1.5 self-stretch rounded-sm ${c.bar} shrink-0`} />
        <div className="text-base shrink-0">{iconFor(f.forma_pagamento)}</div>
        <div className="flex-1 min-w-0">
          <div className={`text-[13px] font-semibold ${c.text} flex items-center gap-2`}>
            {f.forma_pagamento}
            <span className="text-[10px] font-normal text-neutral-500">
              · {fmtNum(f.qtd_transacoes)} transações · {f.pct_volume.toFixed(0)}% do volume
            </span>
          </div>
          {/* Mini-bar do bruto/líquido */}
          <div className="mt-1 flex h-1.5 rounded overflow-hidden bg-neutral-200/60 ring-1 ring-neutral-200/50">
            <div
              className={c.bar}
              style={{ width: `${Math.max((f.liquido / f.bruto) * 100, 2)}%` }}
              title={`Líquido: ${fmtBRL(f.liquido)}`}
            />
            {!semTaxa && (
              <div
                className="bg-neutral-300"
                style={{ width: `${Math.max((f.taxa / f.bruto) * 100, 1)}%` }}
                title={`Taxa: ${fmtBRL(f.taxa)}`}
              />
            )}
          </div>
          <div className="mt-0.5 flex items-center justify-between gap-2 text-[10.5px] text-neutral-600 tabular-nums">
            <span>Bruto {fmtBRL(f.bruto, true)}</span>
            <span>
              Líquido <strong className={c.text}>{fmtBRL(f.liquido, true)}</strong>
            </span>
            <span>
              {semTaxa ? (
                <span className="text-emerald-700 font-semibold">sem taxa</span>
              ) : (
                <>Taxa <strong className="text-rose-600">−{fmtBRL(f.taxa, true)}</strong></>
              )}
            </span>
          </div>
        </div>
        {/* Taxa% — destaque à direita */}
        <div className="text-right shrink-0 tabular-nums">
          <div className={`text-xl font-bold ${c.text}`}>
            {semTaxa ? '0%' : `${f.taxa_pct.toFixed(2)}%`}
          </div>
          <div className="text-[9px] text-neutral-500 uppercase tracking-wider">taxa efetiva</div>
        </div>
      </div>
    </div>
  )
}
