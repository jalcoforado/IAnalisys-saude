import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, KeyRound, Lock, Save, ShieldAlert } from 'lucide-react'

import { usePageTitle } from '@/contexts/PageTitleContext'
import { permissionsService } from '@/services/permissions.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import type { Permission, RoleWithPermissions } from '@/types/permission'

const PROTECTED_ROLES = new Set(['saas_admin', 'tenant_admin'])

const MODULE_LABEL: Record<string, string> = {
  dashboard: 'Dashboards',
  pacientes: 'Pacientes',
  agenda: 'Agenda',
  clinico: 'Clínico',
  financeiro: 'Financeiro',
  sync: 'Sincronização & Analytics',
  usuarios: 'Usuários',
  empresa: 'Empresa',
  ia: 'Assistente IA',
}

const MODULE_ORDER = [
  'dashboard',
  'pacientes',
  'agenda',
  'clinico',
  'financeiro',
  'usuarios',
  'empresa',
  'sync',
  'ia',
]

const ROLE_LABEL: Record<string, string> = {
  tenant_admin: 'Tenant Admin',
  manager: 'Gestor',
  financial: 'Financeiro',
  commercial: 'Comercial',
  operations: 'Operações',
  saas_admin: 'SaaS Admin',
}

const ROLE_ORDER = ['tenant_admin', 'manager', 'financial', 'commercial', 'operations', 'saas_admin']

export default function PermissionsPage() {
  usePageTitle('Permissões', 'Quem vê o quê na sua clínica', 'Empresa')

  const queryClient = useQueryClient()

  // Carrega catálogo + matriz em paralelo
  const [catalogQuery, rolesQuery] = useQueries({
    queries: [
      { queryKey: ['permissions-catalog'], queryFn: permissionsService.listCatalog },
      { queryKey: ['roles-with-permissions'], queryFn: permissionsService.listRoles },
    ],
  })

  // Estado local de edição: roleId -> Set<code>
  const [draft, setDraft] = useState<Record<string, Set<string>>>({})
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; msg: string } | null>(null)

  // Inicializa o draft quando a query chega
  useEffect(() => {
    if (rolesQuery.data) {
      const next: Record<string, Set<string>> = {}
      rolesQuery.data.forEach((r) => {
        next[r.id] = new Set(r.permissions)
      })
      setDraft(next)
    }
  }, [rolesQuery.data])

  // Mutation: salva uma role por vez (mas dispara em paralelo)
  const saveMutation = useMutation({
    mutationFn: async (changes: Array<{ roleId: string; codes: string[] }>) => {
      await Promise.all(
        changes.map(({ roleId, codes }) =>
          permissionsService.updateRolePermissions(roleId, codes),
        ),
      )
    },
    onSuccess: (_data, vars) => {
      setFeedback({
        kind: 'success',
        msg: `${vars.length} role(s) atualizada(s). Próximo login dos usuários afetados aplicará a mudança.`,
      })
      queryClient.invalidateQueries({ queryKey: ['roles-with-permissions'] })
    },
    onError: () => {
      setFeedback({ kind: 'error', msg: 'Falha ao salvar. Tente novamente.' })
    },
  })

  // Permissions agrupadas por módulo
  const grouped = useMemo(() => {
    const out: Record<string, Permission[]> = {}
    ;(catalogQuery.data ?? []).forEach((p) => {
      if (!out[p.module]) out[p.module] = []
      out[p.module].push(p)
    })
    Object.values(out).forEach((arr) => arr.sort((a, b) => a.code.localeCompare(b.code)))
    return out
  }, [catalogQuery.data])

  const orderedModules = useMemo(() => {
    const known = MODULE_ORDER.filter((m) => grouped[m])
    const extra = Object.keys(grouped).filter((m) => !known.includes(m))
    return [...known, ...extra]
  }, [grouped])

  const orderedRoles = useMemo(() => {
    const data = rolesQuery.data ?? []
    return [...data].sort((a, b) => {
      const ai = ROLE_ORDER.indexOf(a.name)
      const bi = ROLE_ORDER.indexOf(b.name)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
  }, [rolesQuery.data])

  // Toggles
  const toggle = (roleId: string, code: string) => {
    setDraft((prev) => {
      const cur = new Set(prev[roleId] ?? [])
      if (cur.has(code)) cur.delete(code)
      else cur.add(code)
      return { ...prev, [roleId]: cur }
    })
  }

  // Diff entre draft e estado original
  const dirtyRoles = useMemo(() => {
    if (!rolesQuery.data) return []
    return rolesQuery.data
      .filter((r) => !PROTECTED_ROLES.has(r.name))
      .filter((r) => {
        const orig = new Set(r.permissions)
        const cur = draft[r.id] ?? new Set()
        if (orig.size !== cur.size) return true
        for (const c of orig) if (!cur.has(c)) return true
        return false
      })
      .map((r) => ({ roleId: r.id, codes: Array.from(draft[r.id] ?? []) }))
  }, [draft, rolesQuery.data])

  if (catalogQuery.isLoading || rolesQuery.isLoading) {
    return (
      <PageContainer>
        <div className="text-sm text-neutral-500">Carregando matriz…</div>
      </PageContainer>
    )
  }

  if (catalogQuery.isError || rolesQuery.isError) {
    return (
      <PageContainer>
        <div className="bg-error-bg border border-error-border rounded-lg p-4 text-sm text-error-text flex items-start gap-3">
          <ShieldAlert size={18} />
          <div>
            <p className="font-semibold">Falha ao carregar permissões.</p>
            <p>Verifique se você tem permissão <code>empresa.permissions.manage</code>.</p>
          </div>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <PageHeader
        eyebrow="EMPRESA"
        title="Matriz de Permissões"
        subtitle="Controle quem vê o quê. Vale para todos os usuários da role"
        icon={<KeyRound size={20} />}
        actions={
          <button
            onClick={() => saveMutation.mutate(dirtyRoles)}
            disabled={dirtyRoles.length === 0 || saveMutation.isPending}
            className="inline-flex items-center gap-2 bg-white/15 hover:bg-white/25 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-3 py-2 rounded-lg ring-1 ring-white/20"
          >
            <Save size={16} />
            {saveMutation.isPending
              ? 'Salvando…'
              : dirtyRoles.length === 0
                ? 'Sem alterações'
                : `Salvar ${dirtyRoles.length} role(s)`}
          </button>
        }
      />

      {feedback && (
        <div
          className={`mb-4 rounded-lg px-4 py-3 text-sm flex items-start gap-3 ${
            feedback.kind === 'success'
              ? 'bg-success-bg border border-success-border text-success-text'
              : 'bg-error-bg border border-error-border text-error-text'
          }`}
        >
          {feedback.kind === 'success' ? <CheckCircle2 size={16} /> : <ShieldAlert size={16} />}
          <span>{feedback.msg}</span>
        </div>
      )}

      {/* Aviso sobre protected roles */}
      <div className="mb-6 rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-600 flex items-start gap-2">
        <Lock size={14} className="mt-0.5 text-neutral-400 shrink-0" />
        <span>
          As roles <strong>tenant_admin</strong> e <strong>saas_admin</strong> sempre têm todas as
          permissões — não podem ser editadas para evitar lock-out.
        </span>
      </div>

      {/* Matriz */}
      <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-neutral-50 border-b border-neutral-200">
              <th className="text-left px-4 py-3 font-medium text-neutral-700 sticky left-0 bg-neutral-50 z-10">
                Permissão
              </th>
              {orderedRoles.map((role) => {
                const isProtected = PROTECTED_ROLES.has(role.name)
                return (
                  <th
                    key={role.id}
                    className="px-3 py-3 font-medium text-neutral-700 text-center min-w-28"
                  >
                    <div className="flex flex-col items-center gap-0.5">
                      <span>{ROLE_LABEL[role.name] ?? role.name}</span>
                      <span className="text-[10px] font-normal text-neutral-400">
                        {isProtected
                          ? 'todas'
                          : `${(draft[role.id]?.size ?? 0)}/${catalogQuery.data?.length ?? 0}`}
                      </span>
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {orderedModules.map((mod) => (
              <ModuleSection
                key={mod}
                moduleKey={mod}
                permissions={grouped[mod]}
                roles={orderedRoles}
                draft={draft}
                onToggle={toggle}
              />
            ))}
          </tbody>
        </table>
      </div>
    </PageContainer>
  )
}

function ModuleSection({
  moduleKey,
  permissions,
  roles,
  draft,
  onToggle,
}: {
  moduleKey: string
  permissions: Permission[]
  roles: RoleWithPermissions[]
  draft: Record<string, Set<string>>
  onToggle: (roleId: string, code: string) => void
}) {
  return (
    <>
      <tr className="bg-neutral-50/60">
        <td
          colSpan={1 + roles.length}
          className="px-4 py-2 text-[11px] font-bold uppercase tracking-wider text-neutral-500 sticky left-0 bg-neutral-50/60"
        >
          {MODULE_LABEL[moduleKey] ?? moduleKey}
        </td>
      </tr>
      {permissions.map((p) => (
        <tr key={p.id} className="border-t border-neutral-100 hover:bg-neutral-50/40">
          <td className="px-4 py-2 sticky left-0 bg-white z-10">
            <div className="flex flex-col">
              <span className="text-neutral-800 font-medium">{p.label}</span>
              <code className="text-[10px] text-neutral-400">{p.code}</code>
            </div>
          </td>
          {roles.map((role) => {
            const isProtected = PROTECTED_ROLES.has(role.name)
            const checked = isProtected
              ? true
              : draft[role.id]?.has(p.code) ?? false
            return (
              <td key={role.id} className="px-3 py-2 text-center">
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={isProtected}
                  onChange={() => onToggle(role.id, p.code)}
                  className="w-4 h-4 rounded border-neutral-300 text-primary-700 focus:ring-primary-500 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                />
              </td>
            )
          })}
        </tr>
      ))}
    </>
  )
}
