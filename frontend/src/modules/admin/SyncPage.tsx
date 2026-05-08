import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'

import { syncService } from '@/services/sync.service'
import { contaAzulService } from '@/services/contaazul.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import {
  STATIC_ENTITIES,
  TRANSACTIONAL_ENTITIES,
  CA_STATIC_ENTITIES,
  CA_TRANSACTIONAL_ENTITIES,
  type SyncEntity,
  type SyncSource,
} from '@/types/sync'
import { SyncProviderPanel, type SyncProviderConfig } from './SyncProviderPanel'

const CLINICORP_CONFIG: SyncProviderConfig = {
  source: 'clinicorp',
  staticEntities: STATIC_ENTITIES,
  heatmapRows: [...TRANSACTIONAL_ENTITIES, 'kpis_monthly' as SyncEntity],
  syncAllStatic: () => syncService.static(),
  syncMonth: (year, month) => syncService.transactionalBatch(year, month),
  syncEntityMonth: (entity, year, month) =>
    syncService.transactional(entity, year, month),
  syncKpisMonth: (year, month) => syncService.kpisMonthly(year, month),
  syncPatientsDetails: () => syncService.clinicorpPatientsDetails(),
  showRebuildPipeline: true,
}

const CONTAAZUL_CONFIG: SyncProviderConfig = {
  source: 'contaazul',
  staticEntities: CA_STATIC_ENTITIES,
  heatmapRows: CA_TRANSACTIONAL_ENTITIES,
  syncAllStatic: () => syncService.contaazulStatic(),
  syncMonth: (year, month) => syncService.contaazulFinancial(year, month),
  syncEntityMonth: (entity, year, month) =>
    syncService.contaazulTransactional(entity, year, month),
  syncAlteracoes: (hoursBack) => syncService.contaazulAlteracoes(hoursBack),
  // Sem kpisMonth — Conta Azul não tem agregado pré-calculado
  // showRebuildPipeline: true — o rebuild é global (cobre CC + CA), faz
  // sentido aparecer nas duas abas pra quem entra direto no CA encontrar.
  showRebuildPipeline: true,
}

const TABS: { key: SyncSource; label: string; subtitle: string; config: SyncProviderConfig }[] = [
  { key: 'clinicorp', label: 'Clinicorp', subtitle: 'agenda · pacientes · receitas · profissionais', config: CLINICORP_CONFIG },
  { key: 'contaazul', label: 'Conta Azul', subtitle: 'pessoas · produtos · serviços · categorias · centros de custo · financeiro', config: CONTAAZUL_CONFIG },
]


export default function SyncPage() {
  usePageTitle('Sincronização', 'Importação · status por entidade · histórico de jobs', 'ADMIN')
  const [activeKey, setActiveKey] = useState<SyncSource>('clinicorp')
  const active = TABS.find((t) => t.key === activeKey) ?? TABS[0]

  return (
    <PageContainer>
      <PageHeader
        eyebrow="ADMIN"
        title="Sincronização"
        subtitle="Importação · status por entidade · histórico de jobs"
        icon={<RefreshCw size={20} />}
      />

      {/* Tabs */}
      <div className="border-b border-neutral-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((t) => {
            const isActive = t.key === activeKey
            return (
              <button
                key={t.key}
                onClick={() => setActiveKey(t.key)}
                className={`pb-3 px-1 text-sm font-medium transition border-b-2 ${
                  isActive
                    ? 'border-primary-700 text-primary-700'
                    : 'border-transparent text-neutral-500 hover:text-neutral-800 hover:border-neutral-300'
                }`}
              >
                <div className="flex flex-col items-start">
                  <span>{t.label}</span>
                  <span className="text-[10px] font-normal text-neutral-400">{t.subtitle}</span>
                </div>
              </button>
            )
          })}
        </nav>
      </div>

      {/* Banner de empresa CA conectada (apenas na aba Conta Azul) */}
      {activeKey === 'contaazul' && <ContaAzulConnectedBanner />}

      {/* Panel */}
      <SyncProviderPanel key={active.key} config={active.config} />
    </PageContainer>
  )
}


function ContaAzulConnectedBanner() {
  const statusQ = useQuery({
    queryKey: ['contaazul', 'status'],
    queryFn: () => contaAzulService.status(),
    refetchInterval: 30_000,
  })
  const s = statusQ.data
  if (!s || !s.connected) return null

  const fmt = s.empresa_nome_fantasia || s.empresa_razao_social
  const cnpjMasked = s.empresa_documento
    ? s.empresa_documento.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')
    : null

  return (
    <div className="bg-success-bg border border-success-border rounded-lg px-4 py-2.5 flex items-center justify-between gap-3 text-sm">
      <div className="flex items-center gap-2 min-w-0">
        <span className="w-2 h-2 rounded-full bg-success-text shrink-0" aria-hidden />
        <div className="truncate">
          <span className="font-medium text-success-text">Conta Azul conectada:</span>{' '}
          <span className="text-neutral-800">{fmt || '—'}</span>
          {cnpjMasked && (
            <span className="text-neutral-500 ml-2 text-xs">CNPJ {cnpjMasked}</span>
          )}
        </div>
      </div>
      {s.empresa_email && (
        <span className="text-xs text-neutral-500 shrink-0 hidden sm:inline">{s.empresa_email}</span>
      )}
    </div>
  )
}
