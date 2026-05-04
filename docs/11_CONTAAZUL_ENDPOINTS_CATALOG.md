# Catálogo de Endpoints — Conta Azul API v2

**Fonte:** documentação oficial recebida em 2026-05-04 (PDF `Introdução às APIs Conta Azul`).
**Base URL:** `https://api-v2.contaazul.com`
**Rate limit:** 600 chamadas/min, 10/seg (por conta conectada). Headers HTTP indicam consumo.
**Auth:** OAuth 2.0 (token expira em 1h, refresh rotaciona).
**Sem webhooks** — sincronização via polling.

## Convenções da API

- **Paginação:** `pagina` (1-indexed) + `tamanho_pagina` (enum: 10, 20, 50, 100, 200, 500, 1000).
  ⚠️ NÃO usar `offset` — silenciosamente ignorado, sempre devolve página 1.
- **Wrappers inconsistentes:**
  - `{"totalItems", "items": [...]}` (en) — pessoas, produtos
  - `{"itens_totais", "itens": [...], "totais": {...}}` (pt) — serviços, eventos financeiros, categorias, **centros de custo**
  - `[...]` array puro — vendedores
  - ⚠ **Doc oficial mente sobre `/v1/centro-de-custo`**: diz wrapper `items` (en), mas o payload real usa `itens` (pt). Confirmado em 2026-05-04.
  - ⚠ **`/v1/centro-de-custo` exige `filtro_rapido=TODOS`** explícito — sem isso, retorna `itens_totais > 0` mas array vazio (bug do CA).
- **Headers obrigatórios em GET:** `Content-Type: application/json` + `Accept: application/json`. Sem isso, 401 mesmo com token válido.
- **Datas:** ISO 8601 (`YYYY-MM-DDTHH:mm:ssZ`).

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
| `/v1/financeiro/categorias-dre` | GET | 🟡 | **DRE estruturada** — útil pro analytics avançado |
| `/v1/conta-financeira` (filtro paginado) | GET | 🟢 | **Contas bancárias/cartões/poupança** — essencial pra fluxo de caixa por banco |
| `/v1/conta-financeira/{id}/saldo-atual` | GET | 🟢 | Saldo em tempo real — cards do dashboard |

### Transacionais — eventos financeiros

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/financeiro/eventos-financeiros/contas-a-receber/buscar` | GET | ✅ | Faturamento — paginado por mês |
| `/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar` | GET | ✅ | Despesas — paginado por mês |
| `/v1/financeiro/eventos-financeiros/parcelas/{id}` | GET | 🟡 | Drill-down de parcela (rateio detalhado) |
| `/v1/financeiro/eventos-financeiros/{id_evento}/parcelas` | GET | 🔵 | Listar parcelas de um evento (já vêm inline na busca) |
| `/v1/financeiro/eventos-financeiros/alteracoes` | GET | 🟢 | **DELTA SYNC** ⭐ — IDs alterados em período. **Economiza muita cota em produção** (vs sync full mensal) |
| `/v1/financeiro/eventos-financeiros/saldo-inicial` | GET | 🟡 | Saldos iniciais por período |
| `/v1/financeiro/transferencias` | GET | 🟡 | Transferências entre contas — reconciliação |
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
| `/v1/venda/busca` (filtro paginado) | GET | 🟡 | **Vendas detalhadas** — útil pra cruzar receita CC ↔ venda CA na IA |
| `/v1/venda/{id}` | GET | 🔵 | Drill-down |
| `/v1/venda/{id_venda}/itens` | GET | 🔵 | Itens da venda |
| `/v1/venda/{id}/imprimir` | GET | 🔵 | PDF |
| `/v1/venda/proximo-numero` | GET | ⚪ | Numeração admin |
| Criar/atualizar/excluir | POST/PUT/POST | ⚪ | — |

---

## 6. Notas Fiscais — `/v1/notas-fiscais*`

| Endpoint | Método | Status | Caso de uso |
|---|---|---|---|
| `/v1/notas-fiscais` (filtro paginado) | GET | 🟡 | NFe emitidas — validar receita declarada vs CA |
| `/v1/notas-fiscais-servico` (filtro paginado) | GET | 🟡 | NFS-e — relevante pra clínica odonto (serviço) |
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

## Recomendações (próximos a implementar)

### Prioridade 1 — operacional
1. **`/v1/pessoas/conta-conectada`** — chamar 1× no callback OAuth pra validar e exibir nome da empresa conectada na UI (`/admin/sync` mostraria "Conectado: Parente Odontologia · CNPJ X")
2. **`/v1/financeiro/eventos-financeiros/alteracoes`** ⭐ **DELTA SYNC** — economiza cota em produção. Em vez de re-sincronizar mês inteiro toda vez, busca só IDs alterados desde o último sync e baixa só esses

### Prioridade 2 — dashboard
3. **`/v1/conta-financeira`** + **saldo-atual** — card "Saldo em conta" no dashboard, fluxo de caixa por banco
4. **`/v1/financeiro/transferencias`** — reconciliação de movimentação entre contas

### Prioridade 3 — análise / IA
5. **`/v1/financeiro/categorias-dre`** — DRE estruturada
6. **`/v1/notas-fiscais-servico`** — NFS-e (clínica emite NFS-e, não NFe) → cruzar com receitas
7. **`/v1/venda/busca`** — vendas detalhadas com itens, pra IA cruzar receita CC ↔ venda CA

### Prioridade 4 — drill-down
8. **`/v1/financeiro/eventos-financeiros/parcelas/{id}`** — detalhe completo de parcela (já vem rateio inline na busca, mas pode ter campos extras)
9. **`/v1/pessoas/{id}`** — detalhe de cliente (endereços completos, contatos extras)

### Não implementar (sem caso de uso na clínica)
- Produtos/cest, ncm, ecommerce-* — fiscais e e-commerce
- Contratos — se Parente usar pacotes/planos, reconsiderar
- Orçamentos — Clinicorp já cobre, e API CA não tem listagem
- Protocolos — só writes
- Pessoas/legado — bridge V1
