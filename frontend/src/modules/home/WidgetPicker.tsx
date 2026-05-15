import { Plus, X } from 'lucide-react'

import {
  filterByPermissions,
  type WidgetMeta,
} from './widgets-catalog'

interface WidgetPickerProps {
  open: boolean
  onClose: () => void
  onAdd: (widget: WidgetMeta) => void
  /** Widgets já presentes no layout — são desabilitados/escondidos no picker. */
  presentIds: string[]
  userPermissions: string[]
}

export function WidgetPicker({
  open,
  onClose,
  onAdd,
  presentIds,
  userPermissions,
}: WidgetPickerProps) {
  if (!open) return null

  const available = filterByPermissions(userPermissions).filter(
    (w) => !presentIds.includes(w.id),
  )

  // Agrupa por categoria
  const byCategory = available.reduce<Record<string, WidgetMeta[]>>((acc, w) => {
    if (!acc[w.category]) acc[w.category] = []
    acc[w.category].push(w)
    return acc
  }, {})

  return (
    <div
      className="fixed inset-0 z-50 bg-neutral-900/40 backdrop-blur-sm flex justify-end"
      onClick={onClose}
    >
      <aside
        className="bg-white h-full w-full max-w-md shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-5 py-4 border-b border-neutral-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-neutral-900">Adicionar widget</h2>
            <p className="text-xs text-neutral-500 mt-0.5">
              {available.length} {available.length === 1 ? 'disponível' : 'disponíveis'} pro seu perfil
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-neutral-100 flex items-center justify-center text-neutral-500"
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {available.length === 0 && (
            <div className="text-center py-10 text-sm text-neutral-500">
              Você já adicionou todos os widgets disponíveis pro seu perfil.
            </div>
          )}

          {Object.entries(byCategory).map(([category, widgets]) => (
            <section key={category}>
              <h3 className="text-[10px] uppercase tracking-wide text-neutral-500 font-bold mb-2">
                {category}
              </h3>
              <div className="space-y-2">
                {widgets.map((w) => {
                  const Icon = w.icon
                  return (
                    <button
                      key={w.id}
                      type="button"
                      onClick={() => onAdd(w)}
                      className="w-full text-left p-3 rounded-lg border border-neutral-200 hover:border-primary-400 hover:bg-primary-50/40 transition-colors flex items-start gap-3 group"
                    >
                      <span className="w-9 h-9 rounded-lg bg-primary-50 text-primary-700 group-hover:bg-primary-100 flex items-center justify-center shrink-0">
                        <Icon size={18} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold text-neutral-900">
                          {w.name}
                        </div>
                        <div className="text-xs text-neutral-500 mt-0.5 line-clamp-2">
                          {w.description}
                        </div>
                      </div>
                      <Plus
                        size={16}
                        className="text-neutral-400 group-hover:text-primary-600 shrink-0 mt-1"
                      />
                    </button>
                  )
                })}
              </div>
            </section>
          ))}
        </div>

        <footer className="px-5 py-3 border-t border-neutral-200 bg-neutral-50 text-xs text-neutral-500">
          Os widgets aparecem filtrados pelas permissões do seu perfil.
        </footer>
      </aside>
    </div>
  )
}
