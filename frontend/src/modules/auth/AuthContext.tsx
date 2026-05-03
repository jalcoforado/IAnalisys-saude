import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import type { ReactNode } from 'react'
import type { UserMe } from '@/types/auth'
import { authService } from '@/services/auth.service'

interface AuthContextValue {
  user: UserMe | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    setUser(null)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await authService.login({ email, password })
      localStorage.setItem('access_token', access_token)
      const me = await authService.me()
      setUser(me)
    },
    []
  )

  // Restaura sessão ao carregar a aplicação
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setIsLoading(false)
      return
    }
    authService
      .me()
      .then(setUser)
      .catch(logout)
      .finally(() => setIsLoading(false))
  }, [logout])

  return (
    <AuthContext.Provider
      value={{ user, isLoading, isAuthenticated: !!user, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
