import {
  AlignVerticalJustifyCenter,
  Check,
  LayoutGrid,
  Maximize2,
  Minimize2,
  PanelLeft,
  PanelTop,
  Palette,
  Sun,
  Moon,
} from 'lucide-react'

import {
  useSettings,
  type LayoutMode,
  type TopbarColor,
} from '@/contexts/SettingsContext'
import { usePageTitle } from '@/contexts/PageTitleContext'

export default function SettingsPage() {
  usePageTitle('Configurações', 'Aparência, layout e preferências', 'ADMIN')
  const { settings, setNavMode, setTopbarColor, setLayoutMode, reset } = useSettings()

  return (
    <main className="px-6 py-6 max-w-5xl mx-auto space-y-6">
      <p className="text-xs text-neutral-500">
        Personalize a aparência e o layout da plataforma. As preferências ficam salvas neste navegador.
      </p>

      <Section title="Layout da navegação" icon={<AlignVerticalJustifyCenter size={16} />} subtitle="Onde ficam os menus principais">
        <OptionGrid>
          <OptionTile
            selected={settings.navMode === 'top'}
            onClick={() => setNavMode('top')}
            icon={<PanelTop size={20} />}
            title="Topo (horizontal)"
            description="Menus na barra superior · padrão"
          />
          <OptionTile
            selected={settings.navMode === 'side'}
            onClick={() => setNavMode('side')}
            icon={<PanelLeft size={20} />}
            title="Lateral (vertical)"
            description="Menus em sidebar fixa à esquerda"
          />
        </OptionGrid>
      </Section>

      <Section title="Largura do conteúdo" icon={<LayoutGrid size={16} />} subtitle="Como o conteúdo das páginas se ajusta à tela">
        <OptionGrid>
          <OptionTile
            selected={settings.layoutMode === 'boxed'}
            onClick={() => setLayoutMode('boxed' as LayoutMode)}
            icon={<Minimize2 size={20} />}
            title="Boxed"
            description="Conteúdo limitado · melhor leitura em monitores grandes"
          />
          <OptionTile
            selected={settings.layoutMode === 'fluid'}
            onClick={() => setLayoutMode('fluid' as LayoutMode)}
            icon={<Maximize2 size={20} />}
            title="Fluid"
            description="Aproveita 100% da largura disponível"
          />
        </OptionGrid>
      </Section>

      <Section title="Cor da barra de navegação" icon={<Palette size={16} />} subtitle="Aparência da topbar/sidebar">
        <OptionGrid cols={3}>
          <ColorTile
            selected={settings.topbarColor === 'light'}
            onClick={() => setTopbarColor('light' as TopbarColor)}
            label="Claro"
            description="Fundo branco · acentos azuis"
            barClass="bg-white border border-neutral-200"
            chipClass="bg-neutral-200"
          />
          <ColorTile
            selected={settings.topbarColor === 'dark'}
            onClick={() => setTopbarColor('dark' as TopbarColor)}
            label="Escuro"
            description="Fundo neutro escuro"
            barClass="bg-neutral-900"
            chipClass="bg-neutral-700"
          />
          <ColorTile
            selected={settings.topbarColor === 'brand'}
            onClick={() => setTopbarColor('brand' as TopbarColor)}
            label="Marca"
            description="Gradiente azul Ianalisys · padrão"
            barClass="bg-gradient-to-r from-primary-700 to-primary-900"
            chipClass="bg-white/30"
          />
        </OptionGrid>
      </Section>

      <Section title="Modo escuro" icon={<Moon size={16} />} subtitle="Tema do conteúdo das páginas">
        <div className="bg-warning-bg border border-warning-border rounded-lg p-4 flex items-center gap-3">
          <Sun size={18} className="text-warning-text shrink-0" />
          <div className="text-xs text-warning-text">
            <strong>Em breve.</strong> Por enquanto a plataforma só está disponível no modo claro.
            Você pode escolher dark na barra de navegação acima.
          </div>
        </div>
      </Section>

      <div className="pt-4 border-t flex items-center justify-between">
        <p className="text-xs text-neutral-500">
          As mudanças são aplicadas instantaneamente e ficam salvas no seu navegador.
        </p>
        <button
          onClick={reset}
          className="text-xs px-3 py-1.5 rounded border border-neutral-300 text-neutral-600 hover:bg-neutral-50"
        >
          Restaurar padrão
        </button>
      </div>
    </main>
  )
}

function Section({ title, icon, subtitle, children }: {
  title: string; icon: React.ReactNode; subtitle?: string; children: React.ReactNode
}) {
  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm p-5">
      <div className="flex items-center gap-2.5 mb-4">
        <span className="w-7 h-7 rounded-lg bg-primary-50 text-primary-700 flex items-center justify-center">{icon}</span>
        <div>
          <h2 className="text-sm font-bold text-neutral-900 leading-tight">{title}</h2>
          {subtitle && <p className="text-xs text-neutral-500">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function OptionGrid({ children, cols = 2 }: { children: React.ReactNode; cols?: number }) {
  return <div className={`grid grid-cols-1 md:grid-cols-${cols} gap-3`}>{children}</div>
}

function OptionTile({ selected, onClick, icon, title, description }: {
  selected: boolean; onClick: () => void;
  icon: React.ReactNode; title: string; description: string
}) {
  return (
    <button
      onClick={onClick}
      className={`relative text-left p-4 rounded-lg border-2 transition ${
        selected ? 'border-primary-600 bg-primary-50' : 'border-neutral-200 hover:border-primary-300'
      }`}
    >
      {selected && (
        <span className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary-600 text-white flex items-center justify-center">
          <Check size={12} />
        </span>
      )}
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${selected ? 'bg-primary-100 text-primary-700' : 'bg-neutral-100 text-neutral-500'}`}>
        {icon}
      </div>
      <div className="mt-3 text-sm font-semibold text-neutral-900">{title}</div>
      <div className="text-xs text-neutral-500 mt-0.5">{description}</div>
    </button>
  )
}

function ColorTile({ selected, onClick, label, description, barClass, chipClass }: {
  selected: boolean; onClick: () => void;
  label: string; description: string; barClass: string; chipClass: string
}) {
  return (
    <button
      onClick={onClick}
      className={`relative text-left p-3 rounded-lg border-2 transition ${
        selected ? 'border-primary-600' : 'border-neutral-200 hover:border-primary-300'
      }`}
    >
      {selected && (
        <span className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary-600 text-white flex items-center justify-center z-10">
          <Check size={12} />
        </span>
      )}
      <div className={`h-12 rounded-md ${barClass} flex items-center px-2 gap-1.5`}>
        <span className={`w-2 h-2 rounded-full ${chipClass}`} />
        <span className={`w-2 h-2 rounded-full ${chipClass}`} />
        <span className={`w-2 h-2 rounded-full ${chipClass}`} />
        <span className="flex-1" />
        <span className={`w-2 h-2 rounded-full ${chipClass}`} />
      </div>
      <div className="mt-3 text-sm font-semibold text-neutral-900">{label}</div>
      <div className="text-xs text-neutral-500 mt-0.5">{description}</div>
    </button>
  )
}
