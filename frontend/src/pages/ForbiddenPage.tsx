import { Link } from 'react-router-dom'
import { Lock } from 'lucide-react'

export default function ForbiddenPage() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center">
        <div className="w-16 h-16 mx-auto rounded-full bg-error-bg text-error-text flex items-center justify-center">
          <Lock size={28} />
        </div>
        <h1 className="text-xl font-bold text-neutral-900 mt-4">Acesso negado</h1>
        <p className="text-sm text-neutral-500 mt-2">
          Você não tem permissão para visualizar esta página. Fale com o
          administrador da sua clínica caso precise de acesso.
        </p>
        <Link
          to="/"
          className="mt-6 inline-block text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800"
        >
          Voltar para o início
        </Link>
      </div>
    </div>
  )
}
