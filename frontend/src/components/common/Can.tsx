import type { ReactNode } from 'react'
import { usePermissions } from '@/hooks/usePermissions'

interface CanProps {
  /** Permission necessária. Se omitido, usar `any` ou `all`. */
  permission?: string
  /** Permite quando tem QUALQUER uma da lista. */
  any?: string[]
  /** Permite só quando tem TODAS da lista. */
  all?: string[]
  /** Conteúdo a renderizar quando autorizado. */
  children: ReactNode
  /** Conteúdo opcional pra negação (default: nada). */
  fallback?: ReactNode
}

/**
 * Esconde/mostra UI baseado em permission do usuário logado.
 * `is_saas_admin = true` é bypass.
 *
 *   <Can permission="financeiro.write"><button>Lançar</button></Can>
 *   <Can any={['pacientes.write','pacientes.export']}>...</Can>
 */
export function Can({ permission, any, all, children, fallback = null }: CanProps) {
  const { has, hasAny, hasAll } = usePermissions()

  let allowed = false
  if (permission) allowed = has(permission)
  else if (any && any.length) allowed = hasAny(...any)
  else if (all && all.length) allowed = hasAll(...all)

  return <>{allowed ? children : fallback}</>
}
