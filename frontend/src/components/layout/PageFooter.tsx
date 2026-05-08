import type { ReactNode } from 'react'

/**
 * Rodapé padrão das páginas internas. Opcional. Usado para meta-informação
 * contextual (data da última sincronização, fonte dos dados, contagem total
 * de registros) e ações secundárias (exportar, baixar relatório).
 *
 * Não é um footer "global" da aplicação — é específico da página. O footer
 * global da aplicação não existe propositalmente: BrandBar + MenuBar já dão
 * contexto suficiente, e dashboards corporativos modernos (Stripe, Linear,
 * Salesforce Lightning) evitam footer global pra maximizar área útil.
 *
 * Visual: barra fina, fundo neutro claro, texto pequeno, separador superior
 * sutil. Aparece sempre no fim do PageContainer.
 */
interface PageFooterProps {
  /** Data ISO do último update dos dados — gera string "Atualizado em ...". */
  lastUpdated?: string | null
  /** Origem dos dados (ex: "Clinicorp + Conta Azul"). */
  dataSource?: string
  /** Conteúdo livre (ações secundárias, links). Aparece à direita. */
  children?: ReactNode
}

const fmtUpdated = (iso: string): string => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function PageFooter({ lastUpdated, dataSource, children }: PageFooterProps) {
  const left: string[] = []
  if (lastUpdated) left.push(`Atualizado em ${fmtUpdated(lastUpdated)}`)
  if (dataSource) left.push(`Fonte: ${dataSource}`)

  if (left.length === 0 && !children) return null

  return (
    <footer className="mt-2 pt-3 border-t border-neutral-200 flex items-center justify-between gap-3 flex-wrap text-[11px] text-neutral-500">
      <div className="flex items-center gap-3 flex-wrap">
        {left.map((txt, i) => (
          <span key={i} className="inline-flex items-center gap-1">
            {i > 0 && <span className="text-neutral-300">·</span>}
            <span>{txt}</span>
          </span>
        ))}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </footer>
  )
}
