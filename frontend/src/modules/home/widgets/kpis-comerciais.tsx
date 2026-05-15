import { CalendarCheck, Percent, UserMinus, Users } from 'lucide-react'

import { KpiWidget, useAnaliseComercialAtual } from './_shared'

export function KpiConsultas() {
  const q = useAnaliseComercialAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.consultas}
      label="Consultas"
      icon={<CalendarCheck size={14} className="text-primary-600" />}
      iconBg="bg-primary-50"
      emphasized
    />
  )
}

export function KpiAbsenteismo() {
  const q = useAnaliseComercialAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.absenteismo_pct}
      label="Absenteísmo"
      icon={<UserMinus size={14} className="text-rose-600" />}
      iconBg="bg-rose-50"
    />
  )
}

export function KpiConversaoComercial() {
  const q = useAnaliseComercialAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.conversao_consulta_orcamento_pct}
      label="Consulta → orçamento"
      icon={<Percent size={14} className="text-amber-600" />}
      iconBg="bg-amber-50"
    />
  )
}

export function KpiPacientesUnicos() {
  const q = useAnaliseComercialAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.pacientes_unicos}
      label="Pacientes únicos"
      icon={<Users size={14} className="text-indigo-600" />}
      iconBg="bg-indigo-50"
    />
  )
}
