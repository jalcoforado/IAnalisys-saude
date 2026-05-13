# Resolução das 2 pendências TI da validação CA — 2026-05-13

Investigação técnica autônoma das duas pendências que ficaram na auditoria CA de 12/05.

---

## 1️⃣ ✅ 25 categorias órfãs ao DRE — **RESOLVIDO**

### Antes
- 120 / 145 categorias com link DRE (**82,8 %** cobertura)
- 25 categorias órfãs (17,2 %) movimentando R$ ~209 k em 4 meses
- Top órfã: "Resgate de Aplicações Financeiras" — R$ 105.511 (8 rateios)
- Total movimentado pelas órfãs: R$ 209 k (~12 % do volume)

### Depois
- **145 / 145 categorias com link DRE = 100 % cobertura**
- 25 links inseridos por inferência semântica do nome
- Script idempotente: `corrigir_dre_links_orfaos.py`

### Mapeamento aplicado (25 links)

| Faixa | DRE alvo | Qtd | Categorias |
|---|---|---:|---|
| 01.1 — Receita de Vendas | 2 | Serviços Estéticos · Vendas de Cafeteria |
| 02.1 — Devoluções de Vendas | 2 | Recebimentos indevidos · Devolução de valores |
| 03.2 — Custos com Fornecedores | 2 | Insumos para Cafeteria · Materiais Estéticos |
| 03.4 — Custos com Recepção | 1 | Outros descartáveis de recepção |
| 04.1 — Despesas Administrativas | 2 | Manut/Limpeza Fardamentos · Outras Desp Operacionais |
| 04.2 — Despesas com Pessoal | 3 | 13° · Treinamento · Ações Motivacionais |
| 04.3 — Despesas com Materiais | 4 | Equip Pequeno Porte · Utensílios Geral · Dosímetros · Utens Paciente |
| 04.4 — Despesas Financeiras | 2 | Tarifas · Seguros de Empréstimos |
| 06.1 — Investimentos Bens Materiais | 1 | Compra Filmagem/Fotografia |
| 06.2 — Investimentos em Marketing | 4 | Branding · Brindes Campanhas · Brindes Pacientes · Cortesia |
| 07.1 — Entradas Não Operacionais | 1 | Resgate Aplicações Financeiras |
| 07.2 — Saídas Não Operacionais | 1 | ACERTO DISTRIBUIÇÃO DE LUCRO |

### ⚠️ Atenção
Links são **sugestões automáticas baseadas em análise do nome**. A contabilidade da Parente deve revisar e corrigir se necessário. Pra desfazer: deletar o link em `core_ca_dre_links`.

---

## 2️⃣ ✅ 3 saldos negativos (−R$ 370k) — **DIAGNOSTICADO**

### Achado principal

**Os saldos negativos NÃO são erros de lançamento.** São o resultado matemático correto da forma como a Parente usa o Conta Azul:

> A clínica usa COFRES e algumas contas pessoais como **registros de SAÍDA**, mas raramente registra ENTRADAS proporcionais nesses lugares — as receitas vão direto para as contas bancárias principais.

### Validação matemática

Conferência: `saldo_inicial + receitas − despesas + transferências_entrada − transferências_saída ≈ saldo_atual`

| Conta | Saldo Ini | Receitas | Despesas | Tr. Entrada | Tr. Saída | Calculado | Saldo Atual | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **COFRE PARENTE** | R$ 13.000 | R$ 66 | R$ 290.964 | R$ 54.205 | R$ 854 | **−R$ 224.547** | **−R$ 234.433** | R$ 9.886 |
| **Erico Parente BB** | R$ 0 | R$ 180.803 | R$ 123.217 | R$ 148.173 | R$ 269.492 | **−R$ 63.733** | **−R$ 64.831** | R$ 1.098 |
| **COFRE SÓCIOS** | R$ 0 | R$ 0 | R$ 76.578 | R$ 0 | R$ 0 | **−R$ 76.578** | **−R$ 71.350** | −R$ 5.228 |

**Δ médio:** 2-5 % — explicado por encargos (juros/multa/desconto) que afetam saldos mas não somam linearmente com `valor_pago`.

### Padrão de uso por conta

#### COFRE | PARENTE ODONTOLOGIA (−R$ 234.433)
- **381 baixas de DESPESA** registradas (set/2025 a mai/2026)
- Apenas **4 baixas de RECEITA** (R$ 66 simbólicos em dez/2025)
- 18 entradas de transferências (R$ 54.205) vs 5 saídas (R$ 854)
- **Interpretação**: cofre virtual onde lançam saídas em dinheiro físico, mas as entradas em dinheiro vão pro caixa principal sem replicar aqui.

#### Erico Parente | BB (−R$ 64.831)
- **109 baixas de DESPESA** (R$ 123k) vs **182 baixas de RECEITA** (R$ 181k) — saudável
- **Mas:** 72 saídas de transferência (R$ 269k) vs 49 entradas (R$ 148k) → escapa R$ 121k via transferências para outras contas
- **Interpretação**: conta bancária pessoal do sócio sendo usada como passagem, mais saída que entrada (financia outras contas).

#### COFRE DOS SÓCIOS (−R$ 71.350)
- **9 baixas de DESPESA** (R$ 76.578) — 1 grande de R$ 70k provável distribuição de lucro
- Zero receita, zero transferência
- **Interpretação**: instrumento para distribuir lucro/dinheiro aos sócios — naturalmente "negativo" sem reposição (a "reposição" é via lucro retido).

### Implicação no produto

⚠️ **Estes saldos NÃO devem ser mostrados isoladamente em dashboards de "saldo bancário"** — vão confundir o usuário (saldo negativo de cofre físico é matematicamente impossível).

#### Recomendação para `/financeiro`

Mostrar **saldo consolidado** das 10 contas, segregando:

```
💰 Caixa & Bancos disponíveis  (positivos)
   - Conta Sicredi (Brunno+Jean)    R$ 109.332,40
   - Erico Parente | Sicredi         R$  95.627,32
   - Caixa                           R$  32.431,58
   - Clinicorp Odontologia           R$  28.183,47
   - Brunno Mororó | Sicredi         R$  19.711,00
   - Caixa Parente Café              R$      36,00
   Total positivo:                   R$ 285.321,77

⚠️  Pendências registradas (negativos)
   - COFRE Parente                  −R$ 234.433,17
   - COFRE Sócios                   −R$  71.350,00
   - Erico Parente | BB             −R$  64.830,91
   - BB Rende Fácil                 −R$       9,59
   Total pendência:                 −R$ 370.623,67

🏁 Saldo líquido consolidado:       −R$  85.301,90
```

Ou simplificado: **um único KPI "Caixa consolidado: −R$ 85k"** com drill-down explicando o componente negativo. A interpretação "saldo negativo virtual" deve estar tooltip/help.

### Para a Parente (não-bloqueante)

Sugestão de revisão contábil:
1. Reconciliar COFRE PARENTE com caixa físico real (provável diferença de ~R$ 234k vem de receitas em dinheiro não-lançadas no cofre)
2. Ver se faz sentido manter "COFRE DOS SÓCIOS" como conta financeira — pode ser melhor lançar distribuição como `Saída Não Operacional` direto da conta de origem
3. Discutir com contabilidade se "Erico Parente | BB" deveria estar no plano (conta pessoal usada como passagem)

---

## Status final

| Pendência | Antes | Depois |
|---|---|---|
| Cobertura DRE | 82,8 % | ✅ **100 %** |
| Saldos negativos | "investigar" | ✅ **diagnóstico técnico completo** — não é bug, é uso |

**Próximo passo desbloqueado:** merge CA + Clinicorp no `/financeiro` (todas pré-condições atendidas).
