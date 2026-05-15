import { LayoutGrid, MousePointerClick, Save, Sparkles } from 'lucide-react'

interface WelcomeModalProps {
  open: boolean
  onConfirm: () => void
  firstName?: string
}

export function WelcomeModal({ open, onConfirm, firstName }: WelcomeModalProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] bg-neutral-900/60 backdrop-blur-sm flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
        <div className="bg-gradient-to-br from-primary-600 to-primary-800 px-6 py-6 text-white">
          <div className="flex items-center gap-3 mb-2">
            <span className="w-10 h-10 rounded-lg bg-white/20 flex items-center justify-center">
              <Sparkles size={20} />
            </span>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-white/70 font-bold">
                Bem-vindo ao
              </div>
              <h2 className="text-2xl font-bold">
                <span className="text-white">MY</span>
                <span className="text-white/70">-Analisys</span>
              </h2>
            </div>
          </div>
          <p className="text-sm text-white/90 leading-relaxed">
            {firstName ? `${firstName}, ` : ''}essa é a sua home. Você começa
            com o painel vazio e escolhe os widgets que importam pra você — pode
            mudar quantas vezes quiser, tudo fica salvo no seu perfil.
          </p>
        </div>

        <div className="px-6 py-5 space-y-4">
          <Step
            icon={<MousePointerClick size={18} />}
            title="Arraste e redimensione"
            description="Clique em “Personalizar” no topo pra entrar no modo edição. Arraste pela área do card, puxe o canto pra redimensionar."
          />
          <Step
            icon={<LayoutGrid size={18} />}
            title="Adicione e remova widgets"
            description="No modo edição, use o “+ Adicionar widget” pra abrir o catálogo filtrado pelo seu perfil. O “×” em cada card remove."
          />
          <Step
            icon={<Save size={18} />}
            title="Salve quando quiser"
            description="“Salvar” persiste no seu perfil. “Cancelar” descarta as mudanças. Sempre dá pra clicar “Resetar pro padrão”."
          />
        </div>

        <div className="px-6 py-4 bg-neutral-50 border-t border-neutral-200 flex justify-end">
          <button
            type="button"
            onClick={onConfirm}
            className="px-5 py-2.5 bg-primary-600 hover:bg-primary-700 text-white text-sm font-bold rounded-lg transition-colors shadow-sm"
          >
            Vamos lá
          </button>
        </div>
      </div>
    </div>
  )
}

function Step({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="w-9 h-9 rounded-lg bg-primary-50 text-primary-700 flex items-center justify-center shrink-0">
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-bold text-neutral-900">{title}</div>
        <div className="text-xs text-neutral-500 mt-0.5 leading-relaxed">
          {description}
        </div>
      </div>
    </div>
  )
}
