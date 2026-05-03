import type { ReactNode } from 'react'
import { usePermissions } from '@/hooks/usePermissions'
import ForbiddenPage from '@/pages/ForbiddenPage'

interface RequirePermissionProps {
  permission?: string
  any?: string[]
  all?: string[]
  children: ReactNode
}

/**
 * Wrapper de rota — bloqueia acesso direto via URL pra usuário sem permission.
 * Usar em conjunto com PrivateRoute (que cuida da autenticação).
 *
 *   <RequirePermission permission="empresa.permissions.manage">
 *     <PermissoesPage />
 *   </RequirePermission>
 */
export default function RequirePermission({
  permission,
  any,
  all,
  children,
}: RequirePermissionProps) {
  const { has, hasAny, hasAll } = usePermissions()

  let allowed = true
  if (permission) allowed = has(permission)
  else if (any && any.length) allowed = hasAny(...any)
  else if (all && all.length) allowed = hasAll(...all)

  if (!allowed) return <ForbiddenPage />
  return <>{children}</>
}
