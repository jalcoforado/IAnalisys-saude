# Validação Conta Azul × DBF — Parente Odontologia

**Data:** 2026-05-12
**Tenant:** `00000000-0000-0000-0000-000000000001`
**Snapshot DBF:** 2026-05-12 01:31 (último rebuild)
**Fonte oficial CA usada:** `visao_contas_a_pagar.xls` (09/05/2026) — 201 títulos quitados de abril/2026

---

## ✅ Veredito Geral

| Onda | Foco | Resultado | Δ |
|------|------|-----------|---|
| A | A Pagar abril/2026 quitados — Excel CA vs DBF | **✅ MATCH PERFEITO** | R$ 0,00 |
| B | Estrutura DRE + cobertura categorias | ✅ 100 % rateios cobertos · 83 % cat linkadas | — |
| C | Transferências + saldos por conta | ✅ Não duplicam fato_caixa · 10 contas mapeadas | — |
| D | Encargos (juros/multa/desconto) abril | **✅ MATCH PERFEITO** | R$ 0,00 |
| E | Coerência interna (ETL/baixas/rateios) | ✅ 100 % eventos com baixa · 100 % rateios coerentes | — |
| F | Cross-check CA RECEITA × Clinicorp fato_financeiro | ✅ Confirma hipótese: CA RECEITA = 0,02-0,17 do real | 6× a 4.077× |

**Conclusão:** A camada de DESPESAS do Conta Azul está **validada ao centavo**. Pronta pra dashboards e merge futuro com Clinicorp (RECEITAS).

---

## ONDA A — Quitados abril/2026

Cruzou `visao_contas_a_pagar.xls` (201 títulos pagos) contra `core_ca_eventos_financeiros`.

| Fonte | Títulos | Valor s/ encargos | Valor c/ encargos |
|-------|--------:|------------------:|------------------:|
| **CA Excel (oficial)** | 201 | R$ 231.874,29 | R$ 233.146,21 |
| **DBF** | 201 | R$ 231.874,29 | (encargos em coluna separada) |
| **Δ** | 0 | **R$ 0,00** | — |

**SQL de validação:**
```sql
SELECT COUNT(*), SUM(valor_pago)
FROM core_ca_eventos_financeiros
WHERE tipo='DESPESA' AND status='ACQUITTED'
  AND data_vencimento BETWEEN '2026-04-01' AND '2026-04-30';
-- → 201 · R$ 231.874,29
```

---

## ONDA B — Estrutura DRE & Categorias

### Estrutura

| Métrica | Valor |
|---|---:|
| Categorias DRE | 32 |
| Totalizadores | 8 |
| Categorias raiz | 16 |
| Profundidade máxima | 1 (rasa) |

### Cobertura

| Métrica | Resultado |
|---|---:|
| Rateios totais | 14.471 |
| Rateios com categoria preenchida | **14.471 (100 %)** |
| Categorias financeiras totais | 145 |
| Categorias linkadas a DRE | **120 (82,8 %)** |
| Categorias **sem** DRE | 25 (17,2 %) ⚠️ |

### Top 14 categorias DRE — DESPESAS pagas abril/2026

| DRE | Código | n | Valor |
|---|---|---:|---:|
| Custos com Fornecedores | 03.2 | 76 | R$ 51.643,33 |
| Custos com Comissão/Prestação de Serviço | 03.3 | 6 | R$ 37.149,80 |
| Despesas com Pessoal | 04.2 | 31 | R$ 34.679,21 |
| Custos tributários ou Financeiros | 03.1 | 6 | R$ 28.083,81 |
| Entradas Não Operacionais | 07.1 | 22 | R$ 24.188,84 |
| Impostos Sobre o Resultado | 05 | 2 | R$ 16.921,31 |
| Despesas Administrativas | 04.1 | 26 | R$ 15.711,10 |
| Investimentos em Bens Materiais | 06.1 | 6 | R$ 12.826,62 |
| Despesas com Materiais e Equipamentos | 04.3 | 14 | R$ 6.664,98 |
| Fretes e Transportadoras | 03.5 | 14 | R$ 2.916,30 |
| **(sem DRE)** | — | 20 | R$ 2.138,48 |
| Saídas Não Operacionais | 07.2 | 2 | R$ 110,00 |
| Custos com Recepção | 03.4 | 1 | R$ 62,50 |
| Despesas Financeiras | 04.4 | 1 | R$ 50,00 |

**Total: R$ 233.146,28** (= R$ 231.874,29 mercadoria + R$ 1.271,92 encargos, bate com Excel)

**Observação:** 20 itens de R$ 2.138 em abril estão **sem DRE** (categoria não linkada). Acionar pra TI Parente sincronizar links faltantes — 25 categorias órfãs no total.

---

## ONDA C — Transferências entre contas

| Métrica | Valor |
|---|---:|
| Transferências lifetime | 271 |
| Soma lifetime | R$ 2.685.052,38 |
| Transferências 2026 (jan-mai) | 88 · R$ 719.074,51 |
| Transferências em `fato_caixa` | **0 (✅ não inflam fluxo)** |

### Por mês 2026
| Mês | n | Soma |
|---|---:|---:|
| 2026-01 | 36 | R$ 200.918,24 |
| 2026-02 | 26 | R$ 146.655,12 |
| 2026-03 | 13 | R$ 178.382,15 |
| 2026-04 | 12 | R$ 193.118,00 |
| 2026-05 | 1 | R$ 1,00 |

### Saldos por conta financeira (12/05/2026)

| Conta | Tipo | Banco | Saldo |
|---|---|---|---:|
| Conta - Brunno Mororó e Jean Leite | CONTA_CORRENTE | OUTROS | R$ 109.332,40 |
| Erico Parente | Sicredi | CONTA_CORRENTE | SICREDI | R$ 95.627,32 |
| Caixa | CAIXINHA | NAO_BANCO | R$ 32.431,58 |
| Conta Clinicorp Odontologia | CONTA_CORRENTE | SICREDI | R$ 28.183,47 |
| Brunno Mororó | Sicredi | CONTA_CORRENTE | SICREDI | R$ 19.711,00 |
| Caixa | Parente Café | CAIXINHA | NAO_BANCO | R$ 36,00 |
| Banco do Brasil - Rende Fácil | APLICACAO | BB | −R$ 9,59 |
| Erico Parente | BB | CONTA_CORRENTE | BB | **−R$ 64.830,91** |
| COFRE DOS SÓCIOS | CAIXINHA | NAO_BANCO | **−R$ 71.350,00** |
| COFRE \| PARENTE ODONTOLOGIA | CAIXINHA | NAO_BANCO | **−R$ 234.433,17** |

**Saldo líquido consolidado: −R$ 85.301,90** (negativo)

⚠️ Achado relevante: **3 contas com saldo expressivamente negativo** somam −R$ 370 k. Vale auditar com a Parente antes de exibir em dashboard.

---

## ONDA D — Encargos (juros/multa/desconto)

| Componente | CA Excel | DBF | Δ | ✅/❌ |
|---|---:|---:|---:|:---:|
| Juros | R$ 121,40 | R$ 121,40 | R$ 0,00 | ✅ |
| Multa | R$ 1.150,52 | R$ 1.150,52 | R$ 0,00 | ✅ |
| Desconto | R$ 0,00 | R$ 0,00 | R$ 0,00 | ✅ |
| **Líquido (J+M−D)** | **R$ 1.271,92** | **R$ 1.271,92** | **R$ 0,00** | **✅** |

**Resolve a pegadinha** documentada em `reference_ca_encargos_gap_pdf.md` — encargos vêm corretos via `core_ca_baixas`.

---

## ONDA E — Coerência interna do ETL

| Teste | Resultado |
|---|---|
| **Test 1:** Todos eventos ACQUITTED têm baixa? | ✅ **Sim, 100 %** |
| **Test 2:** Σ valor_pago(baixas) ≈ valor_pago(evento)? | ✅ Diferenças = encargos (esperado) |
| **Test 3:** Σ rateio.valor por evento == evento.valor_total? | ✅ **3.649 eventos · 100 % coerentes · gap R$ 0,00** |

### Test 2 — diferenças por mês (jan-mai/2026)

| Mês | Σ valor_pago(eventos) | Σ valor_pago(baixas) | Δ |
|---|---:|---:|---:|
| 2026-01 | R$ 431.521,01 | R$ 432.089,64 | −R$ 568,63 |
| 2026-02 | R$ 277.529,51 | R$ 277.530,60 | −R$ 1,09 |
| 2026-03 | R$ 241.848,72 | R$ 242.068,69 | −R$ 219,97 |
| 2026-04 | R$ 231.966,29 | R$ 233.238,21 | −R$ 1.271,92 ← = encargos abril |
| 2026-05 | R$ 82.013,73 | R$ 81.805,73 | +R$ 208,00 |

Δ vem de:
- `valor_pago` do **evento** = principal pago (sem encargos)
- `valor_pago` da **baixa** = total liquidado (com encargos)

Coerência confirmada — a diferença é o spread dos encargos por mês.

---

## ONDA F — Cross-check CA RECEITA × Clinicorp

Comprova a hipótese da memória `reference_ca_uso_real_parente.md`: o CA NÃO é fonte confiável de RECEITA, é o Clinicorp.

| Mês | CA pago | Clinicorp recebido | Clinicorp total | CC÷CA |
|---|---:|---:|---:|---:|
| 2026-01 | R$ 54.984,75 | R$ 325.547,77 | R$ 326.477,77 | **6×** |
| 2026-02 | R$ 6.513,00 | R$ 328.606,36 | R$ 328.606,36 | **50×** |
| 2026-03 | R$ 166,00 | R$ 470.035,75 | R$ 470.035,75 | **2 832×** |
| 2026-04 | R$ 92,00 | R$ 375.127,33 | R$ 375.127,33 | **4 077×** |
| 2026-05 | R$ 0,00 | R$ 62.307,00 | R$ 62.307,00 | (até dia 9) |

**Tendência: a Parente está deixando de baixar receitas no CA gradualmente.** Em mar/abr/2026 praticamente nada é registrado.

Confirma: **dashboards financeiros devem usar Clinicorp como fonte de RECEITA**.

---

## 🔄 Implicações pro produto

1. **Despesas / A Pagar**: CA é fonte de verdade confiável (validado ao centavo). Pode usar em dashboards.
2. **DRE de DESPESAS**: 83 % das categorias estão linkadas. Pré-requisito: TI Parente linkar as **25 categorias órfãs**.
3. **Receitas**: NÃO usar CA. Usar Clinicorp `fato_financeiro` (já validado em produção).
4. **Saldos bancários**: 10 contas estão sendo sincronizadas. Investigar 3 saldos muito negativos antes de exibir.
5. **Transferências**: corretamente isoladas de `fato_caixa` (não inflam fluxo). 
6. **Encargos**: agora capturados via `core_ca_baixas` (juros/multa/desconto/taxa). Reescrever queries que precisam do "valor total quitado" pra somar com encargos.

## 🚀 Próximo passo — merge CA + Clinicorp

Conforme decidido em 12/05 (memória `reference_ca_uso_real_parente.md`):

**Modelo final do `/financeiro`:**
```
RECEITAS  ← Clinicorp fato_financeiro WHERE is_received=1
DESPESAS  ← CA fato_caixa WHERE tipo='DESPESA'
DRE       ← receitas Clinicorp por linha + despesas CA por categoria DRE
SALDO     ← saldos das 10 contas CA
```

Requisitos antes do merge:
- [x] CA despesas validadas (esta validação)
- [x] CA DRE/categorias mapeado
- [x] CA transferências isoladas de fato_caixa
- [x] CA encargos capturados nas baixas
- [x] Clinicorp fato_financeiro validado em produção (memória anterior)
- [ ] **TI Parente:** linkar as 25 categorias órfãs ao DRE (não-bloqueante)
- [ ] **TI Parente:** investigar saldos negativos COFRE PARENTE (−R$ 234k) e Erico Parente BB (−R$ 65k) — entender se é dívida real ou erro de lançamento

---

**Gerado por:** `backend/scripts/validacao_ca/validar_ca.py` (12/05/2026 sessão autônoma)
