import type { ReactNode } from 'react'

/**
 * Cabeçalho padrão das páginas internas. Substitui os "Header" customizados
 * que cada dashboard estava montando à mão (com gradiente, ícone, título e
 * filtros à direita).
 *
 * Anatomia (esquerda → direita):
 *   [ icone ] [ eyebrow ]      [ filters / actions ]
 *            [ TÍTULO   ]
 *            [ subtítulo]
 *
 * Padrão visual: card azul com gradiente sutil, sombra leve, cantos
 * arredondados. Decisão de 2026-05-07 (Pedro): UMA cor única (azul) para
 * todas as páginas — sem distinção por seção. Identidade visual coesa
 * sobrepõe diferenciação por acento.
 *
 * `filters` e `actions` são slots independentes — filtros costumam ser
 * controles persistentes (PeriodSelector, dropdowns), actions são botões
 * de operação (exportar, abrir drawer). Quando ambos existem, filters
 * aparece à esquerda dos actions.
 */
interface PageHeaderProps {
  title: string
  subtitle?: string
  eyebrow?: string
  icon?: ReactNode
  /** Slot à direita pra filtros persistentes (PeriodSelector, dropdowns). */
  filters?: ReactNode
  /** Slot à direita pra ações (botões de export, abrir modal, etc). */
  actions?: ReactNode
}

export function PageHeader({
  title,
  subtitle,
  eyebrow,
  icon,
  filters,
  actions,
}: PageHeaderProps) {
  return (
    <div className="bg-gradient-to-r from-blue-700 to-indigo-700 text-white rounded-xl p-5 flex items-center justify-between gap-4 flex-wrap shadow-md">
      <div className="flex items-center gap-3 min-w-0">
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center shrink-0">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <div className="text-[11px] uppercase tracking-wider font-bold text-blue-200">
              {eyebrow}
            </div>
          )}
          <div className="text-lg font-bold truncate">{title}</div>
          {subtitle && (
            <div className="text-xs text-white/80 truncate">{subtitle}</div>
          )}
        </div>
      </div>
      {(filters || actions) && (
        <div className="flex items-center gap-3 flex-wrap shrink-0">
          {filters}
          {actions}
        </div>
      )}
    </div>
  )
}
