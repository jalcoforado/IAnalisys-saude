import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AlertTriangle, KeyRound, ShieldCheck } from 'lucide-react'

import { authService } from '@/services/auth.service'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-6">
        <div className="max-w-sm w-full bg-white border border-error-border rounded-xl p-6 text-center">
          <span className="w-12 h-12 mx-auto rounded-full bg-error-bg text-error-text flex items-center justify-center">
            <AlertTriangle size={20} />
          </span>
          <h1 className="text-base font-bold text-neutral-900 mt-3">Link inválido</h1>
          <p className="text-xs text-neutral-500 mt-1">
            O link de redefinição precisa de um token. Solicite um novo na tela de recuperação.
          </p>
          <Link
            to="/auth/recuperar-senha"
            className="mt-4 inline-block text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800"
          >
            Solicitar novo link
          </Link>
        </div>
      </div>
    )
  }

  const passwordsMatch = password.length > 0 && password === confirm
  const passwordValid = password.length >= 8

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!passwordValid) {
      setError('A senha precisa ter pelo menos 8 caracteres.')
      return
    }
    if (!passwordsMatch) {
      setError('As senhas não conferem.')
      return
    }

    setLoading(true)
    try {
      await authService.confirmPasswordReset(token, password)
      setSuccess(true)
      setTimeout(() => navigate('/login'), 2500)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Falha ao redefinir senha. O link pode ter expirado.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2">
      <div className="flex flex-col justify-center px-8 py-12 bg-white">
        <div className="max-w-sm w-full mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-neutral-900">Redefinir senha</h1>
            <p className="text-neutral-500 text-sm mt-1">
              Crie uma nova senha. Após confirmar, você poderá entrar com ela.
            </p>
          </div>

          {success ? (
            <div className="bg-success-bg border border-success-border rounded-lg p-4 text-center">
              <span className="w-12 h-12 mx-auto rounded-full bg-white flex items-center justify-center text-success-text">
                <ShieldCheck size={20} />
              </span>
              <p className="text-sm font-semibold text-success-text mt-3">Senha redefinida!</p>
              <p className="text-xs text-success-text/80 mt-1">Redirecionando para o login…</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Nova senha
                </label>
                <div className="relative">
                  <input
                    type={show ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="Mínimo 8 caracteres"
                    className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 pr-16"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600 text-xs"
                  >
                    {show ? 'Ocultar' : 'Mostrar'}
                  </button>
                </div>
                {password.length > 0 && !passwordValid && (
                  <p className="text-[11px] text-warning-text mt-1">
                    Pelo menos 8 caracteres ({password.length}/8).
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Confirmar senha
                </label>
                <input
                  type={show ? 'text' : 'password'}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  placeholder="Repita a senha"
                  className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                {confirm.length > 0 && !passwordsMatch && (
                  <p className="text-[11px] text-error-text mt-1">As senhas não conferem.</p>
                )}
              </div>

              {error && (
                <p className="text-sm text-error-text bg-error-bg border border-error-border rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || !passwordValid || !passwordsMatch}
                className="w-full bg-primary-700 hover:bg-primary-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 rounded-lg text-sm transition"
              >
                {loading ? 'Redefinindo…' : 'Redefinir senha'}
              </button>
            </form>
          )}

          <p className="text-center text-xs text-neutral-400 mt-8">© 2026 IAnalisys Saúde</p>
        </div>
      </div>

      <div className="hidden md:flex flex-col justify-center items-center bg-gradient-to-br from-primary-700 to-primary-900 text-white px-12">
        <div className="max-w-xs text-center space-y-6">
          <KeyRound size={48} className="mx-auto text-primary-200" />
          <h2 className="text-2xl font-bold leading-tight">Crie uma senha forte</h2>
          <ul className="text-primary-200 text-sm text-left space-y-1.5">
            <li>• Mínimo 8 caracteres</li>
            <li>• Não use senhas óbvias (123456, nome, data)</li>
            <li>• Considere usar um gerenciador de senhas</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
