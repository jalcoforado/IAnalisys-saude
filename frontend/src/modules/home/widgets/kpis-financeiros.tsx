import { DollarSign, Percent, Receipt, Wallet } from 'lucide-react'

import { KpiWidget, useAnaliseFinanceiroAtual } from './_shared'

export function KpiFaturamento() {
  const q = useAnaliseFinanceiroAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.faturamento}
      label="Faturamento"
      icon={<DollarSign size={14} className="text-emerald-600" />}
      iconBg="bg-emerald-50"
      emphasized
    />
  )
}

export function KpiRecebido() {
  const q = useAnaliseFinanceiroAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.recebido}
      label="Recebido"
      icon={<Wallet size={14} className="text-primary-600" />}
      iconBg="bg-primary-50"
    />
  )
}

export function KpiTicketMedio() {
  const q = useAnaliseFinanceiroAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.ticket_medio}
      label="Ticket médio"
      icon={<Receipt size={14} className="text-indigo-600" />}
      iconBg="bg-indigo-50"
    />
  )
}

export function KpiConversaoFinanceira() {
  const q = useAnaliseFinanceiroAtual()
  return (
    <KpiWidget
      query={q}
      selectKpi={(d) => d.kpis.conversao}
      label="Conversão (R$ aprov./gerado)"
      icon={<Percent size={14} className="text-amber-600" />}
      iconBg="bg-amber-50"
    />
  )
}
