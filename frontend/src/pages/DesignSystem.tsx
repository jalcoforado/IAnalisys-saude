/**
 * Página de referência visual do Design System IAnalisys
 * Acessível em /design-system (apenas em dev)
 */
export default function DesignSystem() {
  return (
    <div className="container-app py-8 space-y-12">
      <header>
        <h1 className="text-4xl font-bold text-neutral-900">
          IAnalisys Design System
        </h1>
        <p className="text-md text-neutral-500 mt-2">
          Guia de referência visual baseado na identidade da marca
        </p>
      </header>

      {/* Colors */}
      <Section title="Cores">
        <h3 className="text-lg font-semibold text-neutral-700 mb-3">Primary</h3>
        <div className="flex gap-2 flex-wrap">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <ColorSwatch key={shade} name={`primary-${shade}`} className={`bg-primary-${shade}`} />
          ))}
        </div>

        <h3 className="text-lg font-semibold text-neutral-700 mb-3 mt-6">Neutral</h3>
        <div className="flex gap-2 flex-wrap">
          {[50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((shade) => (
            <ColorSwatch key={shade} name={`neutral-${shade}`} className={`bg-neutral-${shade}`} />
          ))}
        </div>

        <h3 className="text-lg font-semibold text-neutral-700 mb-3 mt-6">Semantic</h3>
        <div className="flex gap-4 flex-wrap">
          <div className="alert-success w-40 text-center">Success</div>
          <div className="alert-info w-40 text-center">Info</div>
          <div className="alert-warning w-40 text-center">Warning</div>
          <div className="alert-error w-40 text-center">Error</div>
        </div>
      </Section>

      {/* Typography */}
      <Section title="Tipografia">
        <div className="space-y-3">
          <p className="text-4xl font-bold">Heading 4XL — 36px Bold</p>
          <p className="text-3xl font-bold">Heading 3XL — 30px Bold</p>
          <p className="text-2xl font-semibold">Heading 2XL — 24px Semibold</p>
          <p className="text-xl font-semibold">Heading XL — 20px Semibold</p>
          <p className="text-lg font-medium">Heading LG — 18px Medium</p>
          <p className="text-md">Body MD — 16px Normal</p>
          <p className="text-base">Body Base — 14px Normal</p>
          <p className="text-sm">Body SM — 13px Normal</p>
          <p className="text-xs text-neutral-500">Caption XS — 12px</p>
        </div>
      </Section>

      {/* Buttons */}
      <Section title="Botoes">
        <div className="space-y-4">
          <div className="flex gap-3 items-center flex-wrap">
            <button className="btn-primary btn-sm">Primary SM</button>
            <button className="btn-primary btn-md">Primary MD</button>
            <button className="btn-primary btn-lg">Primary LG</button>
            <button className="btn-primary btn-md" disabled>Disabled</button>
          </div>
          <div className="flex gap-3 items-center flex-wrap">
            <button className="btn-secondary btn-md">Secondary</button>
            <button className="btn-ghost btn-md">Ghost</button>
            <button className="btn-danger btn-md">Danger</button>
          </div>
        </div>
      </Section>

      {/* Inputs */}
      <Section title="Inputs">
        <div className="max-w-md space-y-4">
          <div>
            <label className="label">Nome do paciente</label>
            <input className="input" placeholder="Ex: João Silva" />
            <p className="helper-text">Nome completo do paciente</p>
          </div>
          <div>
            <label className="label">Email</label>
            <input className="input input-error" defaultValue="email-invalido" />
            <p className="error-text">Formato de email invalido</p>
          </div>
          <div>
            <label className="label">Observacoes</label>
            <input className="input" disabled placeholder="Campo desabilitado" />
          </div>
        </div>
      </Section>

      {/* Badges */}
      <Section title="Badges">
        <div className="flex gap-3 flex-wrap">
          <span className="badge-primary">Primary</span>
          <span className="badge-success">Ativo</span>
          <span className="badge-warning">Pendente</span>
          <span className="badge-error">Cancelado</span>
          <span className="badge-neutral">Rascunho</span>
        </div>
      </Section>

      {/* Alerts */}
      <Section title="Alertas">
        <div className="space-y-3 max-w-lg">
          <div className="alert-success">Consulta agendada com sucesso!</div>
          <div className="alert-info">Nova versao do sistema disponivel.</div>
          <div className="alert-warning">Sua licenca expira em 7 dias.</div>
          <div className="alert-error">Erro ao processar pagamento.</div>
        </div>
      </Section>

      {/* Cards */}
      <Section title="Cards">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card">
            <div className="card-header">
              <h3 className="font-semibold text-neutral-900">Pacientes</h3>
            </div>
            <div className="card-body">
              <p className="text-3xl font-bold text-primary-600">1.247</p>
              <p className="text-sm text-neutral-500 mt-1">Total cadastrados</p>
            </div>
          </div>
          <div className="card">
            <div className="card-header">
              <h3 className="font-semibold text-neutral-900">Consultas Hoje</h3>
            </div>
            <div className="card-body">
              <p className="text-3xl font-bold text-success-text">18</p>
              <p className="text-sm text-neutral-500 mt-1">Agendadas</p>
            </div>
          </div>
          <div className="card">
            <div className="card-header">
              <h3 className="font-semibold text-neutral-900">Receita Mensal</h3>
            </div>
            <div className="card-body">
              <p className="text-3xl font-bold text-neutral-900">R$ 45.800</p>
              <p className="text-sm text-neutral-500 mt-1">Maio 2026</p>
            </div>
          </div>
        </div>
      </Section>

      {/* Table */}
      <Section title="Tabela">
        <div className="card overflow-hidden">
          <table className="table">
            <thead>
              <tr>
                <th>Paciente</th>
                <th>Procedimento</th>
                <th>Status</th>
                <th>Valor</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Maria Santos</td>
                <td>Limpeza</td>
                <td><span className="badge-success">Concluido</span></td>
                <td>R$ 250,00</td>
              </tr>
              <tr>
                <td>Carlos Oliveira</td>
                <td>Canal</td>
                <td><span className="badge-warning">Em andamento</span></td>
                <td>R$ 1.200,00</td>
              </tr>
              <tr>
                <td>Ana Lima</td>
                <td>Implante</td>
                <td><span className="badge-primary">Agendado</span></td>
                <td>R$ 3.500,00</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Section>

      {/* Shadows */}
      <Section title="Sombras">
        <div className="flex gap-6 flex-wrap">
          {['shadow-sm', 'shadow', 'shadow-md', 'shadow-lg'].map((s) => (
            <div key={s} className={`${s} bg-white rounded p-6 w-32 text-center text-sm text-neutral-600`}>
              {s}
            </div>
          ))}
        </div>
      </Section>

      {/* Spacing */}
      <Section title="Espacamento (base 16px)">
        <div className="space-y-2">
          {[1, 2, 3, 4, 6, 8, 12, 16].map((s) => (
            <div key={s} className="flex items-center gap-3">
              <span className="text-xs text-neutral-500 w-8">{s}</span>
              <div className={`bg-primary-400 h-3 rounded-sm`} style={{ width: `${s * 4}px` }} />
              <span className="text-xs text-neutral-400">{s * 4}px</span>
            </div>
          ))}
        </div>
      </Section>

      {/* Avatars */}
      <Section title="Avatars">
        <div className="flex gap-3 items-center">
          <div className="avatar avatar-sm">JS</div>
          <div className="avatar avatar-md">MC</div>
          <div className="avatar avatar-lg">AL</div>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-2xl font-semibold text-neutral-900 mb-4 pb-2 border-b border-neutral-200">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ColorSwatch({ name, className }: { name: string; className: string }) {
  return (
    <div className="text-center">
      <div className={`w-16 h-16 rounded border border-neutral-200 ${className}`} />
      <p className="text-xs text-neutral-500 mt-1">{name}</p>
    </div>
  );
}
