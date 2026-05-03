/**
 * TenantContext: carrega TenantSettings do tenant logado e aplica
 * efeitos visuais globais (favicon, primary color via CSS var).
 *
 * Componentes que precisam dos dados do tenant (logo na BrandBar,
 * cores na BrandBar/MenuBar) consomem via useTenant() — qualquer
 * mudança em /empresa/configuracoes invalida a query e propaga.
 */
import { createContext, useContext, useEffect } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'

import { tenantService } from '@/services/tenant.service'
import { useAuth } from '@/modules/auth/AuthContext'
import type { TenantSettings } from '@/types/tenant'

interface TenantContextValue {
  tenant: TenantSettings | null
  isLoading: boolean
  refetch: () => void
}

const TenantContext = createContext<TenantContextValue | null>(null)

export function TenantProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()

  const q = useQuery({
    queryKey: ['tenant', 'settings'],
    queryFn: tenantService.getSettings,
    enabled: isAuthenticated,
    staleTime: 60_000,
  })

  // Aplica favicon dinâmico
  useEffect(() => {
    const url = q.data?.favicon_url
    if (!url) return
    let link = document.querySelector("link[rel*='icon']") as HTMLLinkElement | null
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = url
  }, [q.data?.favicon_url])

  // Aplica title (texto da aba) com nome da empresa
  useEffect(() => {
    if (q.data?.name) document.title = `${q.data.name} · IAnalisys`
  }, [q.data?.name])

  return (
    <TenantContext.Provider value={{ tenant: q.data || null, isLoading: q.isLoading, refetch: q.refetch }}>
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error('useTenant deve ser usado dentro de TenantProvider')
  return ctx
}
