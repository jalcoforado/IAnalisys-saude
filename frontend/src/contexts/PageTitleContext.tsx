import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

interface PageTitle {
  title: string
  subtitle?: string
  /** Pequeno tag/breadcrumb superior — ex: "FINANCEIRO" no flowanalytics. */
  eyebrow?: string
}

interface PageTitleContextValue {
  page: PageTitle
  setPage: (p: PageTitle) => void
}

const PageTitleContext = createContext<PageTitleContextValue | null>(null)

export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [page, setPage] = useState<PageTitle>({ title: 'IAnalisys Saúde' })
  return (
    <PageTitleContext.Provider value={{ page, setPage }}>
      {children}
    </PageTitleContext.Provider>
  )
}

/**
 * Cada página chama esse hook no topo do componente para registrar
 * seu título. O título aparece na BrandBar fixa, sobrevivendo ao scroll.
 *
 * Exemplo:
 *   usePageTitle('Painel Executivo', 'Indicadores estratégicos de Abril/2026', 'ANÁLISE')
 */
export function usePageTitle(title: string, subtitle?: string, eyebrow?: string) {
  const ctx = useContext(PageTitleContext)
  if (!ctx) throw new Error('usePageTitle deve ser usado dentro de PageTitleProvider')
  useEffect(() => {
    ctx.setPage({ title, subtitle, eyebrow })
  }, [title, subtitle, eyebrow])
}

export function usePageTitleValue(): PageTitle {
  const ctx = useContext(PageTitleContext)
  if (!ctx) throw new Error('usePageTitleValue deve ser usado dentro de PageTitleProvider')
  return ctx.page
}
