import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password, tenantId)
      navigate('/')
    } catch {
      setError('Credenciais inválidas ou acesso não autorizado.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2">
      {/* Painel esquerdo — formulário */}
      <div className="flex flex-col justify-center px-8 py-12 bg-white">
        <div className="max-w-sm w-full mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900">IAnalisys Saúde</h1>
            <p className="text-gray-500 text-sm mt-1">Plataforma de inteligência analítica</p>
          </div>

          <h2 className="text-lg font-semibold text-gray-800 mb-6">Acesso ao sistema</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Clínica (Tenant ID)
              </label>
              <input
                type="text"
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                required
                placeholder="ID da clínica"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Usuário
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="seu@email.com"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Senha
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
                >
                  {showPassword ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
            >
              {loading ? 'Entrando...' : 'Acessar plataforma'}
            </button>
          </form>

          <p className="text-center text-xs text-gray-400 mt-8">
            © 2026 IAnalisys Saúde
          </p>
        </div>
      </div>

      {/* Painel direito — branding */}
      <div className="hidden md:flex flex-col justify-center items-center bg-gradient-to-br from-primary-700 to-primary-900 text-white px-12">
        <div className="max-w-xs text-center space-y-6">
          <h2 className="text-3xl font-bold leading-tight">
            Inteligência analítica para clínicas odontológicas
          </h2>
          <p className="text-primary-200 text-sm">
            Centralização de dados, indicadores confiáveis e análises com IA.
          </p>
          <div className="flex flex-wrap justify-center gap-2 pt-2">
            {['Dados em tempo real', 'Análise financeira', 'IA controlada', 'Multi-tenant'].map(
              (chip) => (
                <span
                  key={chip}
                  className="bg-white/15 text-white text-xs px-3 py-1 rounded-full"
                >
                  {chip}
                </span>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
