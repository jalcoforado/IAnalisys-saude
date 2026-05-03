import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Mail } from 'lucide-react'

import { authService } from '@/services/auth.service'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authService.requestPasswordReset(email)
      setSubmitted(true)
    } catch {
      // Mesmo em erro, mostra mensagem genérica — backend já responde 200 sempre
      setSubmitted(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2">
      <div className="flex flex-col justify-center px-8 py-12 bg-white">
        <div className="max-w-sm w-full mx-auto">
          <Link
            to="/login"
            className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-primary-700 mb-6"
          >
            <ArrowLeft size={12} /> Voltar para login
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-bold text-neutral-900">Recuperar senha</h1>
            <p className="text-neutral-500 text-sm mt-1">
              Informe seu email cadastrado e enviaremos um link para redefinir sua senha.
            </p>
          </div>

          {submitted ? (
            <div className="bg-success-bg border border-success-border rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="w-8 h-8 rounded-lg bg-white flex items-center justify-center text-success-text shrink-0">
                  <Mail size={16} />
                </span>
                <div className="text-sm text-success-text">
                  <p className="font-semibold mb-1">Verifique seu email</p>
                  <p className="text-xs leading-relaxed">
                    Se o endereço <strong>{email}</strong> estiver cadastrado, enviamos um link
                    para redefinir sua senha. O link expira em <strong>1 hora</strong>.
                  </p>
                </div>
              </div>
              <Link
                to="/login"
                className="mt-4 block text-center text-xs px-4 py-2 rounded bg-white border border-success-border text-success-text hover:bg-green-50"
              >
                Voltar para o login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="seu@email.com"
                  className="w-full border border-neutral-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              {error && (
                <p className="text-sm text-error-text bg-error-bg border border-error-border rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || !email}
                className="w-full bg-primary-700 hover:bg-primary-800 disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition"
              >
                {loading ? 'Enviando…' : 'Enviar link de redefinição'}
              </button>
            </form>
          )}

          <p className="text-center text-xs text-neutral-400 mt-8">© 2026 IAnalisys Saúde</p>
        </div>
      </div>

      <div className="hidden md:flex flex-col justify-center items-center bg-gradient-to-br from-primary-700 to-primary-900 text-white px-12">
        <div className="max-w-xs text-center space-y-6">
          <Mail size={48} className="mx-auto text-primary-200" />
          <h2 className="text-2xl font-bold leading-tight">Recuperação segura</h2>
          <p className="text-primary-200 text-sm">
            Enviamos um link único e temporário (válido por 1 hora) para o email cadastrado. Não
            compartilhe esse link com ninguém.
          </p>
        </div>
      </div>
    </div>
  )
}
