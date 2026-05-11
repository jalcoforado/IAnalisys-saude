import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import type { SonIAMood } from './SonIAAvatar'

/**
 * Contexto da SonIA — cada página publica seus dados + chave, e o FAB usa
 * isso pra gerar insight contextual quando o usuário o abre. Hoje a análise
 * é heurística (no `analyzers.ts`); na Fase 7 troca pra LLM real sem mudar
 * a interface das páginas.
 */

export interface SonIABullet {
  /** Texto curto, 1-2 linhas. */
  text: string
  /** Tom opcional — colore o marcador. */
  tone?: 'neutral' | 'positive' | 'negative' | 'warning'
}

export interface SonIAInsight {
  mood: SonIAMood
  headline: string
  detail: string
  bullets?: SonIABullet[]
  ctaHref?: string
  ctaLabel?: string
  /** Tag exibida em cima — ex: "Heurístico", "IA". */
  source?: string
}

export interface SonIAPagePublication {
  pageKey: string
  pageTitle: string
  /** Dados arbitrários — o analyzer registrado pra esse pageKey sabe ler. */
  data: unknown
}

interface SonIAContextValue {
  publication: SonIAPagePublication | null
  publish: (p: SonIAPagePublication) => void
  /** Limpa quando a página desmonta — evita FAB analisar dado de outra rota. */
  clear: (pageKey: string) => void
  /** Versão usada pra forçar re-análise (botão "Refazer"). */
  bump: () => void
  bumpToken: number
  /** Estado do painel do FAB — expor permite outros componentes abrirem. */
  open: boolean
  setOpen: (v: boolean) => void
}

const SonIAContext = createContext<SonIAContextValue | null>(null)

export function SonIAProvider({ children }: { children: ReactNode }) {
  const [publication, setPublication] = useState<SonIAPagePublication | null>(null)
  const [bumpToken, setBumpToken] = useState(0)
  const [open, setOpen] = useState(false)
  const currentKeyRef = useRef<string | null>(null)

  const publish = useCallback((p: SonIAPagePublication) => {
    currentKeyRef.current = p.pageKey
    setPublication(p)
  }, [])

  const clear = useCallback((pageKey: string) => {
    if (currentKeyRef.current === pageKey) {
      currentKeyRef.current = null
      setPublication(null)
    }
  }, [])

  const bump = useCallback(() => setBumpToken((t) => t + 1), [])

  const value = useMemo<SonIAContextValue>(
    () => ({ publication, publish, clear, bump, bumpToken, open, setOpen }),
    [publication, publish, clear, bump, bumpToken, open],
  )

  return <SonIAContext.Provider value={value}>{children}</SonIAContext.Provider>
}

export function useSonIA() {
  const ctx = useContext(SonIAContext)
  if (!ctx) throw new Error('useSonIA precisa estar dentro de <SonIAProvider>.')
  return ctx
}
