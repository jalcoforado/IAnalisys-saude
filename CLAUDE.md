# CLAUDE.md

## Contexto

Projeto SaaS multi-tenant para clínicas odontológicas com IA.

## Stack

* Backend: FastAPI
* Frontend: React
* DB: MySQL
* IA: Claude + DeepSeek

## Regras

* usar docs como fonte de verdade
* não criar código fora da arquitetura
* não usar SQL livre
* não acessar staging diretamente
* sempre usar tenant_id

## Primeira tarefa

Criar fundação do projeto:

* estrutura de pastas
* docker-compose
* backend mínimo
* frontend mínimo
* MySQL
* Redis
* .env.example

Não implementar lógica de negócio ainda.
