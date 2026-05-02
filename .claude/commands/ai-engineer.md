Você está implementando o AI Gateway do IAnalisys Saúde.

## Stack
Claude (Anthropic SDK), DeepSeek, Python async, Redis para cache de sessão.

## Arquitetura do AI Gateway

```
Pergunta do usuário
  → Classificador (DeepSeek) — identifica intenção e métricas necessárias
  → Query Engine — monta query controlada nas tabelas analytics
  → Context Builder — busca dados reais e formata contexto
  → LLM Router — decide Claude ou DeepSeek
  → Resposta estruturada
  → Logger — registra tokens, custo, tenant
```

## Regras invioláveis

- **IA nunca acessa banco diretamente** — recebe dados via Query Engine
- **Nunca gerar SQL livre** — usar apenas queries pré-definidas no catálogo
- **Nunca inventar métricas** — usar apenas as métricas oficiais (docs/04)
- **Nunca responder sem dados** — se não há dados, dizer que não há
- **Sempre registrar uso**: tokens_in, tokens_out, modelo, custo, tenant_id
- **Sempre verificar limite** do tenant antes de executar (ai_monthly_token_limit)
- **Sempre respeitar tenant_id** — dados de um tenant nunca vazam para outro

## Roteamento de modelo

| Tipo de pergunta | Modelo | Motivo |
|---|---|---|
| Classificação de intenção | DeepSeek | Rápido, barato |
| Consulta simples (1 métrica) | DeepSeek | Rápido, suficiente |
| Análise comparativa | Claude | Raciocínio complexo |
| Insight executivo | Claude | Qualidade de resposta |
| Resumo de período | Claude | Narrativa coerente |

## Catálogo semântico (queries permitidas)

Apenas estas queries são permitidas no MVP:
- `get_faturamento(tenant_id, from, to)` → fato_financeiro
- `get_inadimplencia(tenant_id, from, to)` → fato_financeiro
- `get_consultas(tenant_id, from, to)` → fato_agenda
- `get_absenteismo(tenant_id, from, to)` → fato_agenda
- `get_conversao_orcamentos(tenant_id, from, to)` → fato_orcamentos
- `get_ticket_medio(tenant_id, from, to)` → fato_financeiro + fato_agenda
- `get_top_profissionais(tenant_id, from, to)` → fato_agenda + dim_profissional

## Formato de resposta obrigatório

```python
class AIResponse(BaseModel):
    value: str           # valor principal ("R$ 45.200,00")
    explanation: str     # explicação em linguagem natural
    period: str          # período analisado ("janeiro a abril de 2026")
    source: str          # tabela/métrica usada ("fato_financeiro.faturamento")
    model_used: str      # "claude" ou "deepseek"
    tokens_used: int
```

## Log de uso obrigatório

Toda chamada deve gravar em `ai_usage_logs`:
- tenant_id
- user_id
- question (resumida, sem PII)
- model_used
- tokens_in, tokens_out
- cost_usd
- response_time_ms
- created_at

## O que não fazer

- Não passar dados raw de pacientes ao modelo (LGPD)
- Não deixar o usuário injetar SQL via pergunta
- Não responder perguntas fora do escopo de dados da clínica
- Não ignorar erro de limite de tokens — retornar erro claro ao usuário
- Não cachear respostas de IA por mais de 1h (dados mudam)

## Referências do projeto
- AI Gateway: docs/06_AI_GATEWAY.md
- Métricas: docs/04_DATABASE_MODEL.md
- Multi-tenant + limites: docs/03_MULTI_TENANT_MODEL.md
