# Arquitetura Técnica

## Stack

Backend:

* Python
* FastAPI
* SQLAlchemy
* MySQL
* Redis

Frontend:

* React
* TypeScript
* Tailwind

IA:

* Claude
* DeepSeek
* AI Gateway próprio

## Estrutura

```
React
↓
FastAPI
↓
Services
↓
MySQL
↓
AI Gateway
```

## Camadas

* staging (dados brutos)
* core (dados tratados)
* analytics (dados para IA)

## Regras

* toda tabela tem tenant_id
* IA não acessa banco direto
* sem SQL livre no MVP
* logs obrigatórios
* separação de camadas

## Backend estrutura

```
api/
services/
repositories/
integrations/
analytics/
ai/
security/
tenants/
workers/
```

## Deploy

* Docker
* MySQL
* Redis

## Testes

* autenticação
* tenant isolation
* métricas
* IA
