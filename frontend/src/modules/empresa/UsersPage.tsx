import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Mail, Plus, ShieldAlert, UserMinus, Users, X } from 'lucide-react'

import { usePageTitle } from '@/contexts/PageTitleContext'
import { usePermissions } from '@/hooks/usePermissions'
import { useAuth } from '@/modules/auth/AuthContext'
import { permissionsService } from '@/services/permissions.service'
import { usersService } from '@/services/users.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import type { UserListItem } from '@/types/user'

const ROLE_LABEL: Record<string, string> = {
  tenant_admin: 'Tenant Admin',
  manager: 'Gestor',
  financial: 'Financeiro',
  commercial: 'Comercial',
  operations: 'Operações',
  saas_admin: 'SaaS Admin',
}

export default function UsersPage() {
  usePageTitle('Usuários', 'Quem tem acesso à clínica', 'Empresa')
  const { user: me } = useAuth()
  const { has } = usePermissions()
  const canInvite = has('usuarios.invite')
  const canEdit = has('usuarios.edit')
  const canDeactivate = has('usuarios.deactivate')
  const queryClient = useQueryClient()

  const usersQuery = useQuery({
    queryKey: ['users-list'],
    queryFn: usersService.list,
  })

  const rolesQuery = useQuery({
    queryKey: ['roles-with-permissions'],
    queryFn: permissionsService.listRoles,
  })

  // Roles disponíveis para atribuir (oculta saas_admin)
  const assignableRoles = useMemo(
    () => (rolesQuery.data ?? []).filter((r) => r.name !== 'saas_admin'),
    [rolesQuery.data],
  )

  const [showInvite, setShowInvite] = useState(false)
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; msg: string } | null>(null)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['users-list'] })
  const announce = (kind: 'success' | 'error', msg: string) => {
    setFeedback({ kind, msg })
    setTimeout(() => setFeedback(null), 4000)
  }

  const inviteMutation = useMutation({
    mutationFn: usersService.invite,
    onSuccess: (data) => {
      announce('success', data.message)
      setShowInvite(false)
      refresh()
    },
    onError: (e: any) => announce('error', e?.response?.data?.detail ?? 'Falha no convite.'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof usersService.update>[1] }) =>
      usersService.update(id, payload),
    onSuccess: () => {
      announce('success', 'Usuário atualizado.')
      refresh()
    },
    onError: (e: any) => announce('error', e?.response?.data?.detail ?? 'Falha ao atualizar.'),
  })

  const deactivateMutation = useMutation({
    mutationFn: usersService.deactivate,
    onSuccess: () => {
      announce('success', 'Usuário desativado.')
      refresh()
    },
    onError: (e: any) => announce('error', e?.response?.data?.detail ?? 'Falha ao desativar.'),
  })

  if (usersQuery.isLoading || rolesQuery.isLoading) {
    return (
      <PageContainer>
        <div className="text-sm text-neutral-500">Carregando usuários…</div>
      </PageContainer>
    )
  }

  if (usersQuery.isError) {
    return (
      <PageContainer>
        <div className="bg-error-bg border border-error-border rounded-lg p-4 text-sm text-error-text flex items-start gap-3">
          <ShieldAlert size={18} />
          <div>
            <p className="font-semibold">Falha ao carregar usuários.</p>
            <p>Verifique se você tem permissão <code>usuarios.read</code>.</p>
          </div>
        </div>
      </PageContainer>
    )
  }

  const users = usersQuery.data ?? []

  return (
    <PageContainer>
      <PageHeader
        eyebrow="EMPRESA"
        title="Usuários"
        subtitle="Cadastre, edite ou desative quem tem acesso à plataforma"
        icon={<Users size={20} />}
        actions={canInvite && (
          <button
            onClick={() => setShowInvite(true)}
            className="inline-flex items-center gap-2 bg-white/15 hover:bg-white/25 text-white text-sm font-medium px-3 py-2 rounded-lg ring-1 ring-white/20"
          >
            <Plus size={16} />
            Convidar usuário
          </button>
        )}
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

      {/* Tabela */}
      <div className="overflow-x-auto rounded-xl border border-neutral-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-neutral-50 border-b border-neutral-200 text-neutral-700">
              <th className="text-left px-4 py-3 font-medium">Nome</th>
              <th className="text-left px-4 py-3 font-medium">Email</th>
              <th className="text-left px-4 py-3 font-medium">Função</th>
              <th className="text-center px-4 py-3 font-medium">Status</th>
              <th className="text-right px-4 py-3 font-medium">Ações</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <UserRow
                key={u.id}
                user={u}
                isMe={u.id === me?.id}
                roles={assignableRoles}
                canEdit={canEdit}
                canDeactivate={canDeactivate}
                onChangeRole={(role_id) => updateMutation.mutate({ id: u.id, payload: { role_id } })}
                onToggleActive={() =>
                  updateMutation.mutate({ id: u.id, payload: { is_active: !u.is_active } })
                }
                onDeactivate={() => deactivateMutation.mutate(u.id)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal de convite */}
      {showInvite && (
        <InviteModal
          onClose={() => setShowInvite(false)}
          onSubmit={(payload) => inviteMutation.mutate(payload)}
          loading={inviteMutation.isPending}
          assignableRoles={assignableRoles}
        />
      )}
    </PageContainer>
  )
}

function UserRow({
  user,
  isMe,
  roles,
  canEdit,
  canDeactivate,
  onChangeRole,
  onToggleActive,
  onDeactivate,
}: {
  user: UserListItem
  isMe: boolean
  roles: { id: string; name: string }[]
  canEdit: boolean
  canDeactivate: boolean
  onChangeRole: (role_id: string) => void
  onToggleActive: () => void
  onDeactivate: () => void
}) {
  const isProtected = user.role_name === 'saas_admin'

  return (
    <tr className="border-t border-neutral-100 hover:bg-neutral-50/40">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-neutral-900">{user.full_name}</span>
          {isMe && (
            <span className="text-[10px] uppercase tracking-wider text-primary-700 bg-primary-50 px-1.5 py-0.5 rounded">
              você
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-neutral-600">{user.email}</td>
      <td className="px-4 py-3">
        {isProtected || isMe || !canEdit ? (
          <span className="text-neutral-700">{ROLE_LABEL[user.role_name] ?? user.role_name}</span>
        ) : (
          <select
            value={user.role_id}
            onChange={(e) => onChangeRole(e.target.value)}
            className="border border-neutral-300 rounded px-2 py-1 text-sm bg-white hover:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {ROLE_LABEL[r.name] ?? r.name}
              </option>
            ))}
          </select>
        )}
      </td>
      <td className="px-4 py-3 text-center">
        {user.is_active ? (
          <span className="inline-block text-[11px] uppercase tracking-wider text-success-text bg-success-bg px-2 py-0.5 rounded-full">
            Ativo
          </span>
        ) : (
          <span className="inline-block text-[11px] uppercase tracking-wider text-neutral-500 bg-neutral-100 px-2 py-0.5 rounded-full">
            Inativo
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        {isMe || isProtected ? (
          <span className="text-xs text-neutral-400">—</span>
        ) : user.is_active && canDeactivate ? (
          <button
            onClick={onDeactivate}
            className="inline-flex items-center gap-1 text-xs text-error-text hover:bg-error-bg px-2 py-1 rounded"
            title="Desativar usuário"
          >
            <UserMinus size={14} /> Desativar
          </button>
        ) : !user.is_active && canEdit ? (
          <button
            onClick={onToggleActive}
            className="inline-flex items-center gap-1 text-xs text-success-text hover:bg-success-bg px-2 py-1 rounded"
            title="Reativar usuário"
          >
            <CheckCircle2 size={14} /> Reativar
          </button>
        ) : (
          <span className="text-xs text-neutral-400">—</span>
        )}
      </td>
    </tr>
  )
}

function InviteModal({
  onClose,
  onSubmit,
  loading,
  assignableRoles,
}: {
  onClose: () => void
  onSubmit: (data: { email: string; full_name: string; role_id: string }) => void
  loading: boolean
  assignableRoles: { id: string; name: string }[]
}) {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  // pré-seleciona role 'commercial' se existir, senão a primeira
  const defaultRole =
    assignableRoles.find((r) => r.name === 'commercial')?.id ?? assignableRoles[0]?.id ?? ''
  const [roleId, setRoleId] = useState(defaultRole)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !fullName || !roleId) return
    onSubmit({ email, full_name: fullName, role_id: roleId })
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center px-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <h2 className="text-base font-bold text-neutral-900">Convidar novo usuário</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-600"
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Nome completo</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              minLength={2}
              placeholder="Nome do usuário"
              className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="usuario@empresa.com.br"
              className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Função</label>
            <select
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
              className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {assignableRoles.map((r) => (
                <option key={r.id} value={r.id}>
                  {ROLE_LABEL[r.name] ?? r.name}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-neutral-500 mt-1">
              A função define o que o usuário poderá ver e editar. Pode ser ajustada depois em
              "Permissões".
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 rounded p-2">
            <Mail size={14} className="text-neutral-400 shrink-0" />
            <span>
              Será enviado um email com link para o usuário definir a senha (válido por 72h).
            </span>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-neutral-600 hover:text-neutral-900 px-3 py-2"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading || !email || !fullName || !roleId}
              className="bg-primary-700 hover:bg-primary-800 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg"
            >
              {loading ? 'Enviando…' : 'Enviar convite'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
