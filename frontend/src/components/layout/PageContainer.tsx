import type { ReactNode } from 'react'

/**
 * Container padrão de páginas internas. Toda página de conteúdo (dashboards,
 * settings, listas, formulários) deve ser envolvida por um PageContainer.
 *
 * Variantes:
 * - default: max-w-7xl (1280px) — padrão para dashboards e listas. Boxed
 *            para legibilidade em monitores wide.
 * - wide:    max-w-[1400px]    — para tabelas/matrizes que exigem mais largura
 *            (ex: matriz de agenda).
 * - narrow:  max-w-5xl (1024px) — formulários, settings, edição de registros.
 *
 * Espaçamento vertical entre filhos: `gap` (default 4 = 1rem).
 *
 * Regra: NÃO use CSS de container ad-hoc dentro das páginas. Sempre passe pelo
 * PageContainer. Layouts cockpit que ocupem 100vw (background com gradiente full
 * bleed) podem usar variant="bleed" e gerenciar a largura interna manualmente.
 */
export type PageContainerVariant = 'default' | 'wide' | 'narrow' | 'bleed'

interface PageContainerProps {
  children: ReactNode
  variant?: PageContainerVariant
  /** Espaçamento vertical entre filhos (Tailwind space-y-X). Default 4. */
  gap?: 3 | 4 | 6
  /** Tag semântica do wrapper. Default 'main'. Use 'div' se já houver <main> acima. */
  as?: 'main' | 'div' | 'section'
  className?: string
}

const VARIANT_CLASSES: Record<PageContainerVariant, string> = {
  default: 'max-w-7xl mx-auto px-6 py-6',
  wide: 'max-w-[1400px] mx-auto px-6 py-6',
  narrow: 'max-w-5xl mx-auto px-6 py-6',
  bleed: 'px-6 py-6',
}

const GAP_CLASS: Record<3 | 4 | 6, string> = {
  3: 'space-y-3',
  4: 'space-y-4',
  6: 'space-y-6',
}

export function PageContainer({
  children,
  variant = 'default',
  gap = 4,
  as: Tag = 'main',
  className = '',
}: PageContainerProps) {
  const cls = `${VARIANT_CLASSES[variant]} ${GAP_CLASS[gap]} ${className}`.trim()
  return <Tag className={cls}>{children}</Tag>
}
