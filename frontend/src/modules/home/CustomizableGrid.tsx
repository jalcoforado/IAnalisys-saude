import { useCallback, useEffect, useMemo, useState } from 'react'
import GridLayout, { WidthProvider } from 'react-grid-layout'
import { Plus, RotateCcw, Save, Settings2, X } from 'lucide-react'

import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'

/** Subset do tipo do callback `onLayoutChange` do react-grid-layout. */
interface RGLLayoutItem {
  i: string
  x: number
  y: number
  w: number
  h: number
}

import type { HomeLayoutItem } from '@/services/home.service'
import type { HomeDashboardResponse } from '@/types/home'

import { getDefaultLayoutForRole } from './default-layouts'
import { useHomeLayout } from './useHomeLayout'
import { WelcomeModal } from './WelcomeModal'
import { WidgetPicker } from './WidgetPicker'
import {
  filterByPermissions,
  findWidget,
  type WidgetMeta,
} from './widgets-catalog'

const ResponsiveGridLayout = WidthProvider(GridLayout)

interface CustomizableGridProps {
  homeData: HomeDashboardResponse
  userRole: string
  userPermissions: string[]
  firstName?: string
}

export function CustomizableGrid({
  homeData,
  userRole,
  userPermissions,
  firstName,
}: CustomizableGridProps) {
  const layoutQuery = useHomeLayout()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<HomeLayoutItem[] | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [welcomeOpen, setWelcomeOpen] = useState(false)

  // Layout efetivo: draft em edição, dados do servidor caso contrário,
  // ou default da role se o user nunca customizou.
  const items: HomeLayoutItem[] = useMemo(() => {
    if (draft) return draft
    if (layoutQuery.data?.layout && layoutQuery.data.layout.length > 0) {
      return layoutQuery.data.layout
    }
    return getDefaultLayoutForRole(userRole)
  }, [draft, layoutQuery.data, userRole])

  // Filtra itens cujos widgets sumiram do catálogo (defensivo) ou que o user
  // perdeu permissão pra ver. Permissions perdidas viram placeholder visível
  // apenas em modo edição pra que o user possa remover.
  const allowedIds = useMemo(() => {
    const allowed = new Set(filterByPermissions(userPermissions).map((w) => w.id))
    return allowed
  }, [userPermissions])

  // Primeiro acesso: layout=null vindo do servidor → boas-vindas.
  useEffect(() => {
    if (layoutQuery.isLoading) return
    if (layoutQuery.data && layoutQuery.data.layout === null) {
      setWelcomeOpen(true)
    }
  }, [layoutQuery.isLoading, layoutQuery.data])

  const startEdit = useCallback(() => {
    setDraft(items)
    setEditing(true)
  }, [items])

  const cancelEdit = useCallback(() => {
    setDraft(null)
    setEditing(false)
    setPickerOpen(false)
  }, [])

  const saveEdit = useCallback(() => {
    if (!draft) {
      setEditing(false)
      return
    }
    layoutQuery.save(draft, {
      onSuccess: () => {
        setDraft(null)
        setEditing(false)
        setPickerOpen(false)
      },
    })
  }, [draft, layoutQuery])

  const resetToDefault = useCallback(() => {
    setDraft(getDefaultLayoutForRole(userRole))
  }, [userRole])

  const removeWidget = useCallback(
    (widgetId: string) => {
      setDraft((d) => (d ?? items).filter((i) => i.widget_id !== widgetId))
    },
    [items],
  )

  const addWidget = useCallback(
    (widget: WidgetMeta) => {
      // Coloca no final do grid (y muito alto — RGL compacta pra cima).
      const maxY = (draft ?? items).reduce(
        (acc, i) => Math.max(acc, i.y + i.h),
        0,
      )
      const newItem: HomeLayoutItem = {
        widget_id: widget.id,
        x: 0,
        y: maxY,
        w: widget.defaultSize.w,
        h: widget.defaultSize.h,
      }
      setDraft((d) => [...(d ?? items), newItem])
      setPickerOpen(false)
    },
    [draft, items],
  )

  const handleLayoutChange = useCallback(
    (rglLayout: RGLLayoutItem[]) => {
      if (!editing) return
      // Mantém só os campos que persistimos. RGL pode mudar a ordem.
      setDraft((current) => {
        const base = current ?? items
        // Indexa por id pra manter widget_ids que sumiram acidentalmente.
        const byId = new Map(base.map((i) => [i.widget_id, i]))
        return rglLayout
          .map<HomeLayoutItem | null>((l) => {
            if (!byId.has(l.i)) return null
            return { widget_id: l.i, x: l.x, y: l.y, w: l.w, h: l.h }
          })
          .filter((x): x is HomeLayoutItem => x !== null)
      })
    },
    [editing, items],
  )

  const handleWelcomeConfirm = useCallback(() => {
    setWelcomeOpen(false)
    // Persiste o default da role como ponto de partida do user.
    layoutQuery.save(getDefaultLayoutForRole(userRole))
  }, [layoutQuery, userRole])

  if (layoutQuery.isLoading) {
    return (
      <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
        Carregando seu painel…
      </div>
    )
  }

  const presentIds = items.map((i) => i.widget_id)

  return (
    <>
      <Toolbar
        editing={editing}
        isSaving={layoutQuery.isSaving}
        onStartEdit={startEdit}
        onCancel={cancelEdit}
        onSave={saveEdit}
        onAdd={() => setPickerOpen(true)}
        onReset={resetToDefault}
      />

      <ResponsiveGridLayout
        className={editing ? 'rgl-editing' : ''}
        layout={items.map((i) => {
          const meta = findWidget(i.widget_id)
          return {
            i: i.widget_id,
            x: i.x,
            y: i.y,
            w: i.w,
            h: i.h,
            minW: meta?.minSize.w ?? 2,
            minH: meta?.minSize.h ?? 2,
          }
        })}
        cols={12}
        rowHeight={60}
        margin={[12, 12]}
        containerPadding={[0, 0]}
        isDraggable={editing}
        isResizable={editing}
        draggableCancel=".rgl-no-drag"
        onLayoutChange={handleLayoutChange}
      >
        {items.map((item) => {
          const meta = findWidget(item.widget_id)
          const hasPermission = meta && allowedIds.has(meta.id)
          const content =
            meta && hasPermission ? meta.render(homeData) : null

          return (
            <div
              key={item.widget_id}
              className={`relative ${editing ? 'ring-2 ring-primary-300 ring-offset-2 rounded-xl' : ''}`}
            >
              {editing && (
                <button
                  type="button"
                  onClick={() => removeWidget(item.widget_id)}
                  className="rgl-no-drag absolute -top-2 -right-2 z-20 w-7 h-7 rounded-full bg-error-DEFAULT text-white shadow-md hover:scale-110 transition-transform flex items-center justify-center"
                  title="Remover widget"
                  aria-label="Remover widget"
                >
                  <X size={14} />
                </button>
              )}
              {content ?? (
                <PlaceholderCard
                  name={meta?.name ?? item.widget_id}
                  reason={
                    !meta
                      ? 'Widget desconhecido'
                      : !hasPermission
                      ? 'Sem permissão pra ver este widget'
                      : 'Sem dados disponíveis no momento'
                  }
                />
              )}
            </div>
          )
        })}
      </ResponsiveGridLayout>

      <WidgetPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onAdd={addWidget}
        presentIds={presentIds}
        userPermissions={userPermissions}
      />

      <WelcomeModal
        open={welcomeOpen}
        onConfirm={handleWelcomeConfirm}
        firstName={firstName}
      />
    </>
  )
}

function Toolbar({
  editing,
  isSaving,
  onStartEdit,
  onCancel,
  onSave,
  onAdd,
  onReset,
}: {
  editing: boolean
  isSaving: boolean
  onStartEdit: () => void
  onCancel: () => void
  onSave: () => void
  onAdd: () => void
  onReset: () => void
}) {
  if (!editing) {
    return (
      <div className="flex justify-end mb-3">
        <button
          type="button"
          onClick={onStartEdit}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-neutral-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors"
        >
          <Settings2 size={14} /> Personalizar painel
        </button>
      </div>
    )
  }

  return (
    <div className="bg-primary-50 border border-primary-200 rounded-xl p-3 mb-4 flex items-center justify-between gap-3 flex-wrap">
      <div className="text-xs text-primary-900">
        <strong>Modo edição</strong> — arraste os cards, redimensione pelo canto ou
        use o <strong>×</strong> pra remover.
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-primary-700 bg-white border border-primary-300 hover:bg-primary-100 rounded-lg transition-colors"
        >
          <Plus size={14} /> Adicionar widget
        </button>
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-neutral-600 bg-white border border-neutral-300 hover:bg-neutral-100 rounded-lg transition-colors"
          title="Volta pro layout padrão da sua role"
        >
          <RotateCcw size={14} /> Resetar
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-neutral-600 hover:bg-neutral-100 rounded-lg transition-colors"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-primary-600 hover:bg-primary-700 disabled:opacity-60 rounded-lg transition-colors shadow-sm"
        >
          <Save size={14} /> {isSaving ? 'Salvando…' : 'Salvar'}
        </button>
      </div>
    </div>
  )
}

function PlaceholderCard({ name, reason }: { name: string; reason: string }) {
  return (
    <div className="bg-neutral-50 border-2 border-dashed border-neutral-300 rounded-xl h-full p-4 flex flex-col items-center justify-center text-center">
      <div className="text-sm font-bold text-neutral-500 mb-1">{name}</div>
      <div className="text-xs text-neutral-400">{reason}</div>
    </div>
  )
}
