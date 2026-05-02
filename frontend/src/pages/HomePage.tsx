import { Link } from 'react-router-dom'

function HomePage() {
  return (
    <div className="min-h-screen bg-neutral-50 flex flex-col items-center justify-center px-6">
      <div className="text-center max-w-md">
        <h1 className="text-3xl font-bold text-primary-700 mb-2">
          IAnalisys Saúde
        </h1>
        <p className="text-neutral-500 text-sm">
          Plataforma de inteligência analítica para clínicas odontológicas
        </p>

        <div className="mt-8 grid gap-3">
          <Link
            to="/admin/sync"
            className="block bg-white border rounded-lg px-4 py-3 text-left hover:border-primary-300 transition"
          >
            <div className="text-sm font-semibold text-neutral-900">Sincronização Clinicorp</div>
            <div className="text-xs text-neutral-500 mt-0.5">Importar dados manualmente · status por entidade · histórico de jobs</div>
          </Link>
        </div>
      </div>
    </div>
  )
}

export default HomePage
