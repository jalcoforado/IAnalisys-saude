Você está desenvolvendo o frontend do IAnalisys Saúde.

## Stack
React 18, TypeScript (strict), Tailwind CSS 3, React Router v6, Axios, TanStack Query v5.

## Estrutura obrigatória

```
src/
  components/common/    → botões, inputs, cards, badges reutilizáveis
  components/layout/    → sidebar, topbar, page wrapper
  modules/
    dashboard/          → visão geral executiva
    financeiro/         → módulo financeiro
    comercial/          → orçamentos + vendas
    operacional/        → agendamentos
    assistente/         → chat IA
    admin/              → gestão do tenant
  pages/                → monta layout + módulo (sem lógica)
  services/             → chamadas à API (axios)
  hooks/                → useAuth, useTenant, hooks de dados
  theme/                → cores, tokens de design
  types/                → interfaces TypeScript globais
```

## Regras invioláveis

- **Sempre** TypeScript — sem `any`, sem `as unknown`
- **Nunca** chamar API direto no componente — usar hook ou TanStack Query
- **Nunca** colocar regra de negócio no frontend — só apresentação
- **Sempre** separar componente de dados: componente recebe props, hook busca dados
- **Sempre** tipar props com `interface`, não `type` para objetos de componente
- Formulários: React Hook Form
- Dados remotos: TanStack Query (`useQuery`, `useMutation`)
- Rotas protegidas: verificar token via `useAuth` hook

## Padrão de chamada à API

```typescript
// services/financeiro.service.ts
import api from '@/services/api'
import type { FinanceiroKPIs } from '@/types/financeiro'

export const getKPIs = (from: string, to: string) =>
  api.get<FinanceiroKPIs>('/financeiro/kpis', { params: { from, to } })
```

```typescript
// hooks/useFinanceiroKPIs.ts
import { useQuery } from '@tanstack/react-query'
import { getKPIs } from '@/services/financeiro.service'

export const useFinanceiroKPIs = (from: string, to: string) =>
  useQuery({
    queryKey: ['financeiro', 'kpis', from, to],
    queryFn: () => getKPIs(from, to).then(r => r.data),
  })
```

## Design system

Paleta baseada no SIG 2026 (sistema de referência):
- Primary: #1A56DB (azul)
- Success: #057A55 (verde)
- Danger: #C81E1E (vermelho)
- Warning: #9F580A (laranja)
- Background: #F0F2F5

## O que não fazer

- Não duplicar lógica entre módulos
- Não criar layout hardcoded sem responsividade
- Não misturar dados com UI no mesmo componente
- Não usar `useEffect` para buscar dados — usar TanStack Query
- Não importar diretamente de `axios` — sempre via `@/services/api`

## Referências do projeto
- Visão e módulos: docs/01_PRODUCT_VISION.md
- Arquitetura frontend: docs/02_ARCHITECTURE.md
