import { useCallback, useEffect, useMemo, useState } from 'react'
import GridLayout, { WidthProvider } from 'react-grid-layout'
import { LayoutGrid, Plus, Save, Trash2, X } from 'lucide-react'

import { HOME_START_EDIT_EVENT } from '@/config/menus'

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
  userPermissions: string[]
  firstName?: string
}

export function CustomizableGrid({
  homeData,
  userPermissions,
  firstName,
}: CustomizableGridProps) {
  const layoutQuery = useHomeLayout()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<HomeLayoutItem[] | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [welcomeOpen, setWelcomeOpen] = useState(false)

  // Layout efetivo: draft em edição, dados do servidor caso contrário,
  // ou array vazio se o user nunca customizou (começa do zero — UX opção A).
  const items: HomeLayoutItem[] = useMemo(() => {
    if (draft) return draft
    return layoutQuery.data?.layout ?? []
  }, [draft, layoutQuery.data])

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

  // Escuta o trigger global do UserMenu (item "Personalizar painel").
  useEffect(() => {
    const handler = () => {
      setDraft(items)
      setEditing(true)
    }
    window.addEventListener(HOME_START_EDIT_EVENT, handler)
    return () => window.removeEventListener(HOME_START_EDIT_EVENT, handler)
  }, [items])

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

  const esvaziarPainel = useCallback(() => {
    const ok = window.confirm(
      'Esvaziar o painel? Você poderá adicionar widgets de novo via "Adicionar widget".',
    )
    if (!ok) return
    layoutQuery.save([], {
      onSuccess: () => {
        // Reload completo: garante que o react-grid-layout descarte qualquer
        // state interno residual ao limpar o layout.
        window.location.reload()
      },
      onError: () => {
        alert('Erro ao esvaziar o painel. Tente novamente.')
      },
    })
  }, [layoutQuery])

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
    // Persiste layout vazio — user começa do zero e adiciona widgets via
    // "Personalizar painel" → "Adicionar widget".
    layoutQuery.save([])
  }, [layoutQuery])

  if (layoutQuery.isLoading) {
    return (
      <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
        Carregando seu painel…
      </div>
    )
  }

  const presentIds = items.map((i) => i.widget_id)

  // Empty state em modo view: painel sem widgets configurados.
  const showEmptyState = !editing && items.length === 0 && !welcomeOpen

  return (
    <>
      <Toolbar
        editing={editing}
        isSaving={layoutQuery.isSaving}
        onCancel={cancelEdit}
        onSave={saveEdit}
        onAdd={() => setPickerOpen(true)}
        onReset={esvaziarPainel}
      />

      {showEmptyState && (
        <div className="bg-white border-2 border-dashed border-neutral-300 rounded-xl p-12 text-center">
          <div className="w-14 h-14 rounded-full bg-primary-50 text-primary-600 flex items-center justify-center mx-auto mb-4">
            <LayoutGrid size={26} />
          </div>
          <h3 className="text-base font-bold text-neutral-900 mb-1">
            Seu MY-Analisys está vazio
          </h3>
          <p className="text-sm text-neutral-500 max-w-md mx-auto mb-5">
            Abra o menu do seu perfil (canto inferior esquerdo) e escolha
            <strong> Personalizar painel</strong> — ou clique no botão abaixo pra começar agora.
          </p>
          <button
            type="button"
            onClick={startEdit}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-bold text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors shadow-sm"
          >
            <LayoutGrid size={14} /> Personalizar agora
          </button>
        </div>
      )}

      {(items.length > 0 || editing) && (
      <ResponsiveGridLayout
        // Força remount quando o layout muda drasticamente (reset, mudança de versão
        // após save). Sem isso, o state interno do RGL pode reter widgets antigos.
        key={`rgl-v${layoutQuery.data?.version ?? 0}-${items.length}`}
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
              // overflow-hidden: impede que widgets com mais conteúdo que o container
              // vazem por cima dos vizinhos abaixo.
              // [&>*]:h-full / [&>section]:h-full: força o card filho (qualquer tag)
              // a preencher 100% da altura do grid item — sem isso, cards com conteúdo
              // curto (KPI sem insight, Absenteísmo etc.) ficam visualmente menores
              // que os outros na mesma linha.
              className={`relative overflow-hidden [&>div]:h-full [&>section]:h-full ${
                editing ? 'ring-2 ring-primary-300 ring-offset-2 rounded-xl' : ''
              }`}
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
      )}

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
  onCancel,
  onSave,
  onAdd,
  onReset,
}: {
  editing: boolean
  isSaving: boolean
  onCancel: () => void
  onSave: () => void
  onAdd: () => void
  onReset: () => void
}) {
  // Quando não está editando, o toolbar fica oculto — o trigger de edição
  // vive no UserMenu (item "Personalizar painel") que dispara o evento global.
  if (!editing) return null

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
          title="Remove todos os widgets — você adiciona de novo via 'Adicionar widget'"
        >
          <Trash2 size={14} /> Esvaziar
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
