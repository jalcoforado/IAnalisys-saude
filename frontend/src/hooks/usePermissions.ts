import { useAuth } from '@/modules/auth/AuthContext'

/**
 * Hook único pra checar permissions do usuário logado.
 *
 * - `is_saas_admin` é bypass — sempre `true` em qualquer check
 * - `has(code)` — tem essa permission?
 * - `hasAny(...codes)` — tem pelo menos uma?
 * - `hasAll(...codes)` — tem todas?
 */
export function usePermissions() {
  const { user } = useAuth()
  const isAdmin = !!user?.is_saas_admin
  const set = new Set(user?.permissions ?? [])

  const has = (code: string) => isAdmin || set.has(code)
  const hasAny = (...codes: string[]) => isAdmin || codes.some((c) => set.has(c))
  const hasAll = (...codes: string[]) => isAdmin || codes.every((c) => set.has(c))

  return { has, hasAny, hasAll, isSaasAdmin: isAdmin }
}
