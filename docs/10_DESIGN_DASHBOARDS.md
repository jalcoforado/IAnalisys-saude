# 10 — Padrão de Design para Dashboards Estratégicos

Referência visual e princípios para construir dashboards executivos que comuniquem informação de **alto nível** para tomada de decisão estratégica. Não é um documento de tokens (esses estão em `frontend/src/theme/`); é um guia sobre como **estruturar e apresentar** as informações.

---

## 1. Inspiração de referência

A linha visual segue o padrão do **flowanalytics** (referência aprovada por Pedro em 2026-05-03):

- Header com saudação personalizada (ex: "Olá Laura 🎉") e mascote/ilustração 3D
- **Hero card** com o número-chave gigantesco (faturamento total, etc.) em destaque visual
- KPIs em cards com:
  - **Ícone colorido em badge** (quadrado com background pastel) à esquerda do número
  - Número grande, peso bold, tabular-nums
  - **Duas linhas de comparação**: vs período anterior (MoM) **E** vs ano anterior (YoY) — não apenas uma
  - Setas ▲▼ coloridas (verde/vermelho) por direção da variação
- Tabelas de "top N" com avatar/ícone à esquerda, valor à direita, **barra de progresso** indicando peso relativo
- Ranking visual com **medalhas** (1ª, 2ª, 3ª posição) para destacar os top performers
- Cards-resumo de números importantes (ex: "Clientes Novos 33", "Clientes Aniversário 60") com ícone grande circular ao lado do número
- Gauge semicircular para % de meta
- Radar chart para performance multidimensional
- Disposição em **grid responsivo** com cards de tamanhos variados (não tudo igual) — o que é mais importante ocupa mais espaço

## 2. Princípios

### 2.1 Cada número deve ter contexto

Um KPI sozinho não decide nada. Sempre exiba:
- **Valor atual** em destaque
- **Variação MoM** (mês vs mês anterior)
- **Variação YoY** (mesmo mês ano anterior)
- Subtítulo opcional com a fonte ("de 2.341 na base", "59 dias úteis", etc.)

Para variações invertidas (absenteísmo, inadimplência) — queda é boa — use a cor **verde para queda** e vermelho para alta.

### 2.2 Hierarquia visual clara

Três níveis de destaque:
1. **Hero** (1-2 números mais críticos) — fonte 3xl-4xl, card maior, possivelmente cor de marca
2. **KPIs principais** (4-6 cards) — fonte 2xl, grid uniforme
3. **Detalhamento** (tabelas, gráficos) — densidade alta, fonte sm

### 2.3 Cor com propósito, não decoração

- Cor de marca (azul primary-700) → ações principais, hero, pipeline
- Verde (success) → recebido, ativo, crescimento
- Amarelo/Laranja (warning) → em risco, em followup, atenção
- Vermelho (error) → perdido, recusado, alerta crítico
- Cinza (neutral) → contexto, labels, valores neutros
- **Pastéis** (success-bg, warning-bg, info-bg) → backgrounds de badges de ícone

### 2.4 Densidade calibrada

Dashboards executivos não são "telas vazias bonitas", mas também não são paineis BI saturados. A regra:
- 1 informação primária por card
- Detalhamento (% e valor anterior) em texto menor abaixo
- Sem mais de 3 cores por card (1 destaque + 1 fundo + 1 texto)

### 2.5 Gráficos servem a decisões

Cada gráfico deve responder a uma pergunta:
- **Bar chart 12 meses** → "estamos crescendo?"
- **Donut mix de pagamento** → "de onde vem o dinheiro?"
- **Curva ABC bar** → "quem são os 20% mais valiosos?"
- **Donut churn buckets** → "qual fatia da base está em risco?"

Se o gráfico não responde a uma pergunta clara, é decoração — corte.

## 3. Componentes-padrão (a serem extraídos para `components/dashboard/`)

### 3.1 `<KpiCard>`

```
[ícone colorido]   FATURAMENTO
                   R$ 369.205
                   ▼ -20.8% MoM   ▲ +69.0% YoY
                   vs R$ 466k     vs R$ 218k
```

Estrutura:
- Badge quadrado 40×40px com background pastel + ícone lucide (cor primária)
- Label em uppercase neutral-500 11px tracking-wide
- Número 2xl bold tabular-nums
- Linha 1: variação MoM com seta + cor + valor anterior em parênteses
- Linha 2: variação YoY com seta + cor + valor anterior

### 3.2 `<TopRankingCard>`

```
🥇 1º TACIENE        R$ 244.614   ▓▓▓▓▓▓▓▓▓▓ 100%
🥈 2º ILLYANA M.     R$ 143.797   ▓▓▓▓▓▓░░░░  58%
🥉 3º LUIZ P.        R$ 27.814    ▓░░░░░░░░░  11%
   4º ERICO A.       R$ 1.890     ░░░░░░░░░░   1%
```

Medalhas só nas 3 primeiras posições, barra de progresso normalizada pelo top1.

### 3.3 `<HeroNumber>`

Para o KPI mais importante da tela. Card grande, número 4xl-5xl, cor de marca, com decoração lateral (ilustração ou pattern sutil).

### 3.4 `<MetricBadge>`

Pequeno componente para variação MoM/YoY: seta + valor + cor automática:

```tsx
<MetricBadge value={-20.78} label="MoM" inverse={false} />
// renderiza: ▼ -20.8% MoM (vermelho)
```

## 4. Iconografia

Biblioteca: **lucide-react** (leve, tree-shakeable, ~80kb). Mapeamento sugerido:

| KPI/Seção          | Ícone lucide        |
| ------------------ | ------------------- |
| Faturamento        | `TrendingUp`        |
| Consultas          | `CalendarCheck`     |
| Conversão          | `Target`            |
| Absenteísmo        | `CalendarX`         |
| Ticket médio       | `Receipt`           |
| Pacientes ativos   | `Users`             |
| Pipeline           | `Wallet`            |
| Inadimplência      | `AlertTriangle`     |
| Top profissional   | `Award` / `Trophy`  |
| Categorias agenda  | `LayoutGrid`        |
| Curva ABC          | `BarChart3`         |
| Churn / risco      | `UserMinus`         |
| LTV                | `Gem`               |
| Novos pacientes    | `UserPlus`          |
| Recorrentes        | `RotateCcw`         |

Sempre dentro de badge quadrado com background pastel: `bg-primary-50 text-primary-700`, `bg-success-bg text-success-text`, etc.

## 5. Dados que SEMPRE devem aparecer

Para qualquer dashboard executivo, garantir mínimo:

- [x] Período selecionável (mês + ano)
- [x] Comparação **MoM** explícita (não apenas implícita no card)
- [x] Comparação **YoY** explícita
- [x] Subtítulo dizendo **a base do cálculo** ("recebido em fato_financeiro", "da base de 2.341")
- [x] Indicação visual de carregamento, erro, e estado vazio (não apenas "—")

## 6. Pitfalls a evitar

- ❌ Cards uniformes demais (perde hierarquia — o que importa some)
- ❌ Gráficos decorativos sem pergunta clara
- ❌ Cor sem semântica (azul "porque é bonito")
- ❌ Densidade excessiva em uma única view (preferir scroll com seções)
- ❌ Variação MoM sem dizer que é MoM (dúvida = perda de confiança)
- ❌ Tooltips como única fonte de informação crítica (gestor escaneia, não passa o mouse)

## 7. Aplicado ao IAnalisys Saúde

Estado atual em `frontend/src/modules/dashboard/DashboardPage.tsx`:

- ✅ 6 KPIs Hero
- ✅ Comparação YoY em card separado
- ✅ Funil comercial em 5 etapas
- ✅ Mix de pagamento (donut + tabela)
- ✅ Top profissionais (tabela)
- ✅ Top categorias (tabela)
- ✅ Curva ABC (bar chart)
- ✅ Churn buckets (donut)
- ✅ Top 10 LTV (tabela)
- ✅ Novos vs recorrentes (card com barras)

Pendente para alinhar com o padrão deste documento:

- [ ] **MoM E YoY explícitos no Hero** (hoje só MoM)
- [ ] Ícones lucide em badges coloridos nos KPIs
- [ ] Top profissionais como ranking visual com medalhas
- [ ] Saudação no topo do header
- [ ] Card hero único para o número principal (faturamento total ou pipeline)
- [ ] Barras de progresso normalizadas em listas de top N

---

**Última atualização:** 2026-05-03 — versão 1 após validação visual em abril/2026.
