import { AlertCircle, Heart, Repeat, TrendingUp } from 'lucide-react'

import { KpiWidget, useAnalisePacientesAtual } from './_shared'

export function KpiPacientesAtivos() {
  const q = useAnalisePacientesAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.pacientes_ativos}
      label="Pacientes ativos"
      icon={<Heart size={14} className="text-emerald-600" />}
      iconBg="bg-emerald-50"
      emphasized
    />
  )
}

export function KpiRecorrencia() {
  const q = useAnalisePacientesAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.taxa_recorrencia_pct}
      label="Recorrência"
      icon={<Repeat size={14} className="text-primary-600" />}
      iconBg="bg-primary-50"
    />
  )
}

export function KpiLtvMedio() {
  const q = useAnalisePacientesAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.ltv_medio}
      label="LTV médio"
      icon={<TrendingUp size={14} className="text-indigo-600" />}
      iconBg="bg-indigo-50"
    />
  )
}

export function KpiEmRisco() {
  const q = useAnalisePacientesAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.em_risco_qty}
      label="Em risco"
      icon={<AlertCircle size={14} className="text-amber-600" />}
      iconBg="bg-amber-50"
    />
  )
}
