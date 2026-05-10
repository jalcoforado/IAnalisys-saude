# Catálogo de Endpoints — Conta Azul API v2

**Fonte:** documentação oficial recebida em 2026-05-04 (PDF `Introdução às APIs Conta Azul`).
**Base URL:** `https://api-v2.contaazul.com`
**Rate limit:** 600 chamadas/min, 10/seg (por conta conectada). Headers HTTP indicam consumo.
**Auth:** OAuth 2.0 (token expira em 1h, refresh rotaciona).
**Sem webhooks** — sincronização via polling.

## Convenções da API

- **Paginação:** `pagina` (1-indexed) + `tamanho_pagina`.
  - Maioria aceita enum 10/20/50/100/200/500/1000.
  - ⚠ **NF-e e NFS-e** aceitam **apenas 10/20/50/100** (validado 2026-05-09).
  - NÃO usar `offset` — silenciosamente ignorado, sempre devolve página 1.
- **Wrappers inconsistentes:**
  - `{"totalItems", "items": [...]}` (en) — pessoas, produtos
  - `{"itens_totais", "itens": [...], "totais": {...}}` (pt) — serviços, eventos financeiros, categorias, **centros de custo**, **conta-financeira**, **transferências**, **categorias-dre**, **saldo-inicial**
  - `{"saldo_atual": <number>}` — endpoint de saldo individual
  - `[...]` array puro — vendedores
  - ⚠ **Doc oficial mente sobre `/v1/centro-de-custo`**: diz wrapper `items` (en), mas o payload real usa `itens` (pt). Confirmado em 2026-05-04.
  - ⚠ **`/v1/centro-de-custo` exige `filtro_rapido=TODOS`** explícito — sem isso, retorna `itens_totais > 0` mas array vazio (bug do CA).
- **Headers obrigatórios em GET:** `Content-Type: application/json` + `Accept: application/json`. Sem isso, 401 mesmo com token válido.
- **Datas — formatos descobertos (validado 2026-05-09):**
  - **`saldo-inicial`** exige ISO 8601 datetime **SEM Z** (ex: `2026-04-01T00:00:00`). `Z` no final causa 400 com mensagem dizendo o formato esperado.
  - **`transferências`** aceita ISO 8601 datetime **com ou sem Z** (`2026-04-01T00:00:00` funciona). Parâmetros são `data_inicio` + `data_fim` — ambos obrigatórios.
  - **`venda/busca`** idem — `data_inicio` + `data_fim`.
  - Eventos financeiros (contas-a-receber/pagar): aceita date simples também (`2026-04-01`).
- **NFS-e e NFe têm campos obrigatórios não-óbvios:** mensagem de erro genérica ("Campos obrigatórios não informados"). Tentamos `data_inicio/fim`, `data_emissao_inicio/fim`, `situacao` — todos retornaram 400. Provavelmente exige campo extra (id_pessoa? numero?) — investigar com doc específica de NF antes de tentar implementar.

## Legenda de status / prioridade

| Símbolo | Significado |
|---|---|
| ✅ | Implementado e funcionando |
| 🟢 | Alta prioridade — essencial pra dashboard/drill-down/operação |
| 🟡 | Média prioridade — útil pra IA ou análise futura |
| 🔵 | Baixa — operacional/admin, raro |
| ⚪ | N/A — só faz sentido em writes (POST/PATCH/DELETE) |

---

## 1. Pessoas — `/v1/pessoas/*`

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/pessoas` (filtro paginado) | GET | ✅ | Sync clientes + fornecedores. Wrapper `items` (en) |
| `/v1/pessoas/{id}` | GET | 🟡 | Drill-down completo (endereço, contatos extras) |
| `/v1/pessoas/conta-conectada` | GET | 🟢 | **Validar empresa conectada** — usar 1× ao conectar OAuth |
| `/v1/pessoas/legado/{id}` | GET | 🔵 | Bridge ID legado V1 (não usamos) |
| Criar/ativar/inativar/excluir | POST | ⚪ | Não vamos escrever no CA por enquanto |
| Atualizar | PUT/PATCH | ⚪ | — |

---

## 2. Produtos — `/v1/produtos/*`

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/produtos` (filtro paginado) | GET | ✅ | Sync catálogo |
| `/v1/produtos/{id}` | GET | 🟡 | Drill-down (estoque, fiscal, variações) |
| `/v1/produtos/categorias` | GET | 🔵 | Categorias de produto (não confundir com cat. financeiras) |
| `/v1/produtos/cest` | GET | 🔵 | Fiscal — irrelevante pra clínica odonto |
| `/v1/produtos/ncm` | GET | 🔵 | Fiscal — irrelevante |
| `/v1/produtos/unidades-medida` | GET | 🔵 | Lookup admin |
| `/v1/produtos/ecommerce-categorias` | GET | 🔵 | E-commerce — irrelevante |
| `/v1/produtos/ecommerce-marcas` | GET | 🔵 | E-commerce — irrelevante |
| Criar/atualizar/deletar | POST/PATCH/DELETE | ⚪ | — |

---

## 3. Serviços — `/v1/servicos/*`

⚠️ **Inconsistência detectada:** nosso `client.py` chama `/v1/servico` (singular), doc oficial diz `/v1/servicos` (plural). Funcionou no smoke-test; provavelmente singular é endpoint legado/alias. **Validar e migrar pro plural quando possível.**

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/servicos` (filtro paginado) | GET | ✅ (via `/servico` legado) | Catálogo de serviços odontológicos |
| `/v1/servicos/{id}` | GET | 🔵 | Drill-down |
| Criar/atualizar/deletar | POST/PATCH/DELETE | ⚪ | — |

---

## 4. Financeiro — `/v1/financeiro/*` + `/v1/categorias` + `/v1/centro-de-custo` + `/v1/conta-financeira`

**Coração da integração.** Tudo aqui é prioridade alta ou média.

### Cadastros mestres (estáticos)

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/categorias` (filtro paginado) | GET | ✅ | Lookup categoria (RECEITA/DESPESA) + hierarquia pai/filho |
| `/v1/centro-de-custo` (filtro paginado) | GET | ✅ | Lookup CC (Parente não usa, mas estrutura tá pronta) |
| `/v1/financeiro/categorias-dre` | GET | 🟡 explorado 2026-05-09 | **DRE estruturada** — 16 categorias raiz hierárquicas com `subitens[]` e `categorias_financeiras[]` que vinculam às categorias planas. Wrapper `{"itens": [...]}` |
| `/v1/conta-financeira` (filtro paginado) | GET | 🟢 explorado 2026-05-09 | **Contas bancárias** — 36 contas em Parente (23 ativas). Campos: `id, banco, codigo_banco, nome, ativo, tipo, conta_padrao, agencia, numero, possui_config_boleto_bancario`. Tipos: CORRENTE, APLICACAO, etc. |
| `/v1/conta-financeira/{id}/saldo-atual` | GET | 🟢 explorado 2026-05-09 | Saldo em tempo real — wrapper `{"saldo_atual": <number>}`. Funciona pra todas contas (ex: aplicação BB Parente = R$ -9,59) |

### Transacionais — eventos financeiros

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/financeiro/eventos-financeiros/contas-a-receber/buscar` | GET | ✅ | Faturamento — paginado por mês |
| `/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar` | GET | ✅ | Despesas — paginado por mês |
| `/v1/financeiro/eventos-financeiros/parcelas/{id}` | GET | 🟢 explorado 2026-05-09 | **Drill-down de parcela** — única fonte de `juros`, `multa`, `desconto` realizados (NÃO vêm em `/buscar`) + `data_pagamento` real + `metodo_pagamento` + `conta_financeira_destino` + `conciliado`. Wrapper `{baixas: [...], rateios: [...], ...}`. Implementado via `sync_baixas_parcelas` (semaphore=3 + retry 429). Sem encargo, gap PDF vs `/buscar` fica ~R$ 1-2k/mês. |
| `/v1/financeiro/eventos-financeiros/{id_evento}/parcelas` | GET | 🔵 | Listar parcelas de um evento (já vêm inline na busca) |
| `/v1/financeiro/eventos-financeiros/alteracoes` | GET | 🟢 | **DELTA SYNC** ⭐ — IDs alterados em período. **Economiza muita cota em produção** (vs sync full mensal) |
| `/v1/financeiro/eventos-financeiros/saldo-inicial` | GET | 🟡 explorado 2026-05-09 | Saldos iniciais por conta+período. Campos: `tipo (RECEITA/DESPESA), id_conta_financeira, data_competencia, saldo_inicial`. **Exige datetime SEM Z**: `2026-04-01T00:00:00` |
| `/v1/financeiro/transferencias` | GET | 🟡 explorado 2026-05-09 | Transferências entre contas (12 em abr/26 Parente). Campos: `id, descricao, valor, data, origem{conta_financeira{id,nome}, composicao_valor{...}}, destino{...}`. **`data_inicio` + `data_fim` obrigatórios** |
| Criar evento receber/pagar | POST | ⚪ | — |
| Atualizar parcela | PATCH | ⚪ | — |

### Baixas (acquittance)

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/financeiro/eventos-financeiros/parcelas/{parcela_id}/baixa` | GET | 🟡 | Baixas de uma parcela (auditoria de pagamento) |
| `/v1/financeiro/eventos-financeiros/parcelas/baixa/{baixa_id}` | GET | 🔵 | Detalhe de baixa específica |
| Criar/atualizar/deletar baixa | POST/PATCH/DELETE | ⚪ | — |

### Cobranças (charges)

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/financeiro/eventos-financeiros/contas-a-receber/cobranca/{id}` | GET | 🔵 | Cobrança bancária (Parente provavelmente não usa) |
| Criar/deletar cobrança | POST/DELETE | ⚪ | — |

---

## 5. Vendas — `/v1/venda/*`

⚠️ Atenção: prefixo é `/venda/` (singular) embora a entidade seja "vendas".

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/venda/vendedores` | GET | ✅ | Lookup (array puro) |
| `/v1/venda/busca` (filtro paginado) | GET | 🟡 explorado 2026-05-09 | **Vendas detalhadas** — wrapper `{"totais", "quantidades", "total_itens", "itens"}`. Campos: `id, id_legado, data, criado_em, data_alteracao, tipo (SALE), itens (PRODUCT/SERVICE), condicao_pagamento, total, numero, cliente{id,nome,email}, versao, situacao{nome,descricao}, origem`. Exige `data_inicio` + `data_fim` |
| `/v1/venda/{id}` | GET | 🔵 | Drill-down |
| `/v1/venda/{id_venda}/itens` | GET | 🔵 | Itens da venda |
| `/v1/venda/{id}/imprimir` | GET | 🔵 | PDF |
| `/v1/venda/proximo-numero` | GET | ⚪ | Numeração admin |
| Criar/atualizar/excluir | POST/PUT/POST | ⚪ | — |

---

## 6. Notas Fiscais — `/v1/notas-fiscais*`

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/notas-fiscais` (filtro paginado) | GET | ⚠ explorado 2026-05-09 | NFe emitidas — **400 com "Campos obrigatórios não informados"** mesmo passando `data_inicio/fim`, `data_emissao_inicio/fim`, `situacao`. Investigar doc específica antes de implementar |
| `/v1/notas-fiscais-servico` (filtro paginado) | GET | ⚠ explorado 2026-05-09 | NFS-e — mesmo erro 400 do NFe. **Apenas tamanho_pagina 10/20/50/100 aceito** (não 5). Provavelmente exige campo extra (id_pessoa? id_servico?) — investigar |
| `/v1/notas-fiscais/{chave}` | GET | 🔵 | Detalhe por chave de acesso |
| Vincular NF a MDFe | POST | ⚪ | — |

---

## 7. Contratos (vendas agendadas) — `/v1/contratos/*`

Só faz sentido se a Parente vender pacotes recorrentes (planos mensais de tratamento, mensalidade etc.). **Confirmar com Pedro antes de implementar.**

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/contratos` (filtro paginado) | GET | 🔵 | Listar contratos — só se Parente usar |
| `/v1/contratos/{id}` | GET | 🔵 | Drill-down |
| `/v1/contratos/proximo-numero` | GET | ⚪ | Admin |
| Criar/encerrar/remover | POST/DELETE | ⚪ | — |

---

## 8. Orçamentos — `/v1/orcamentos/*`

⚠️ A API só expõe **detalhe por id** e POST/DELETE — **não tem listagem GET**. Pra puxar todos teria que conhecer os IDs.

A Parente usa orçamentos no Clinicorp (já cobrimos via `StgCcEstimates`), então CA orçamentos é **redundante**. Pular.

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/orcamentos/{id}` | GET | ⚪ | Sem listagem; uso esporádico |
| Criar/excluir | POST/DELETE | ⚪ | — |

---

## 9. Protocolos — `/v1/protocolo/{id}`

Status de eventos assíncronos enviados via POST. Como não vamos **escrever** no CA, irrelevante.

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/protocolo/{id}` | GET | ⚪ | Só pra writes assíncronos (não fazemos) |

---

## Plano "Show no Financeiro" — 4 fases (definido 2026-05-09)

Após exploração de 7 endpoints CA prioritários, plano consolidado:

### Fase 1 — Saldo Bancário ⭐ (impacto visual imediato) ✅ entregue 2026-05-09
- Sync `/v1/conta-financeira` (36 contas em Parente, 23 ativas)
- Sync `/v1/conta-financeira/{id}/saldo-atual` (1×/dia, em paralelo asyncio.gather)
- Sync `/v1/financeiro/eventos-financeiros/saldo-inicial` (saldo histórico mensal)
- Dashboard ganha: card **"Saldo total"** + breakdown por banco + linha 12m
- **Onda 1 fix:** `_is_banco_real()` separa CAIXINHA/NAO_BANCO (cofres contábeis) — saldo Parente passou de -R$ 85k → +R$ 188k

### Fase 2 — DRE Estruturada ✅ entregue 2026-05-09
- Sync `/v1/financeiro/categorias-dre` (16 categorias raiz hierárquicas)
- Linka `categorias_financeiras[]` planas com pais DRE (já temos as planas em `core_ca_categorias`)
- Dashboard ganha **DRE navegável** (drill: "Receitas Op → Vendas → categorias")
- Smoke abr/26: 16 raízes → 32 nós, 120 links, 98% classificado

### Onda 2 — Detalhar baixas + Encargos ✅ entregue 2026-05-09
- Sync `/v1/financeiro/contas-pagar-receber/parcelas/{id}` via `sync_baixas_parcelas` (semaphore=3, retry 429)
- Migration 0031: `core_ca_baixas` com data_pagamento real, método, conta destino, conciliado, juros/multa/desconto
- `FinanceiroOverview` ganhou `metodos_pagamento` + `conciliacao` + `kpis.encargos_{entradas,saidas}`
- **Validação PDF abr/26:** Saídas R$ 233.146 = `fato_caixa` R$ 231.874 + encargos R$ 1.272 (gap fechou em R$ 0)

### Fase 3 — Transferências
- Sync `/v1/financeiro/transferencias` (12 em abr/26)
- Separa transferências internas das despesas/receitas — corrige distorção atual no fluxo

### Fase 4 — Vendas detalhadas + Match CC ↔ CA (= PR-16 do roadmap)
- Sync `/v1/venda/busca` + itens
- Match: orçamento CC aprovado ↔ venda CA registrada

## Pendentes futuros (não bloqueantes)

- **`/v1/financeiro/eventos-financeiros/alteracoes`** ⭐ DELTA SYNC (economia em produção — só faz sentido com sync automático ativado)
- **`/v1/financeiro/eventos-financeiros/parcelas/{id}`** — drill-down parcela (rateio inline)
- **`/v1/pessoas/{id}`** — detalhe de cliente
- **`/v1/notas-fiscais-servico`** — investigar quais campos obrigatórios são (resposta API genérica)

## Não implementar (sem caso de uso)
- Produtos/cest, ncm, ecommerce-* — fiscais e e-commerce
- Contratos — se Parente usar pacotes/planos, reconsiderar
- Orçamentos — Clinicorp já cobre, e API CA não tem listagem
- Protocolos — só writes
- Pessoas/legado — bridge V1
