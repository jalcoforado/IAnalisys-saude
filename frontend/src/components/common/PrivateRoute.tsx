import { Navigate } from 'react-router-dom'
import { useAuth } from '@/modules/auth/AuthContext'

interface Props {
  children: React.ReactNode
}

export default function PrivateRoute({ children }: Props) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-400 text-sm">Carregando...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
