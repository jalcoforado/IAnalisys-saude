import { useState } from 'react'

import { syncService } from '@/services/sync.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
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
  showRebuildPipeline: true,
}

const CONTAAZUL_CONFIG: SyncProviderConfig = {
  source: 'contaazul',
  staticEntities: CA_STATIC_ENTITIES,
  heatmapRows: CA_TRANSACTIONAL_ENTITIES,
  syncAllStatic: () => syncService.contaazulStatic(),
  syncMonth: (year, month) => syncService.contaazulFinancial(year, month),
  // Sem entityMonth nem kpisMonth — Conta Azul só roda batch do mês inteiro
  showRebuildPipeline: false,
}

const TABS: { key: SyncSource; label: string; subtitle: string; config: SyncProviderConfig }[] = [
  { key: 'clinicorp', label: 'Clinicorp', subtitle: 'agenda · pacientes · receitas · profissionais', config: CLINICORP_CONFIG },
  { key: 'contaazul', label: 'Conta Azul', subtitle: 'pessoas · financeiro · produtos · serviços', config: CONTAAZUL_CONFIG },
]


export default function SyncPage() {
  usePageTitle('Sincronização', 'Importação · status por entidade · histórico de jobs', 'ADMIN')
  const [activeKey, setActiveKey] = useState<SyncSource>('clinicorp')
  const active = TABS.find((t) => t.key === activeKey) ?? TABS[0]

  return (
    <main className="px-6 py-6 max-w-7xl mx-auto space-y-4">
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

      {/* Panel */}
      <SyncProviderPanel key={active.key} config={active.config} />
    </main>
  )
}
