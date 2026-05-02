# AI Gateway

## Objetivo

Centralizar uso de IA com controle total.

## Modelos

* Claude
* DeepSeek

## Fluxo

```
Pergunta → Gateway → valida → executa → responde
```

## Regras

* IA não acessa banco direto
* usa métricas definidas
* usa queries controladas

## Uso por modelo

**DeepSeek:**

* classificação
* tarefas simples

**Claude:**

* análise
* insights
* respostas executivas

## Controle

* tokens por tenant
* custo por tenant
* logs obrigatórios

## Segurança

* respeitar permissões
* respeitar tenant
* não expor dados sensíveis

## Resposta

* valor
* explicação
* período
* fonte
