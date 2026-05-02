# IAnalisys Saúde

Plataforma SaaS multi-tenant de inteligência analítica com IA para clínicas odontológicas.

## O que é

Sistema que centraliza dados operacionais (Clinicorp) e financeiros (Conta Azul), gerando indicadores confiáveis e análises com IA para apoiar decisões gerenciais de clínicas odontológicas.

## Status atual do projeto

> **Fase: Fundação arquitetural**

A estrutura de pastas, configurações base e serviços de infraestrutura estão definidos. As seguintes funcionalidades **ainda não estão implementadas** nesta fase:

- Autenticação e controle de acesso
- Migrations de banco de dados
- Dashboards e módulos de visualização
- Integrações com Clinicorp e Conta Azul
- AI Gateway e modelos de IA (Claude, DeepSeek)

O desenvolvimento segue a ordem definida nos documentos da pasta `docs/`.

## Stack

| Camada    | Tecnologia                              |
| --------- | --------------------------------------- |
| Backend   | Python 3.12, FastAPI                    |
| ORM       | SQLAlchemy (async), Alembic (migrations)|
| Frontend  | React 18, TypeScript, Tailwind          |
| Banco     | MySQL 8.0                               |
| Cache/Fila| Redis 7                                 |
| IA        | Claude, DeepSeek (previsto)             |

## Pré-requisitos

- Docker e Docker Compose
- Node.js 20+ (desenvolvimento local)
- Python 3.12+ (desenvolvimento local)

## Como rodar com Docker

```bash
# 1. Copiar variáveis de ambiente
cp .env.example .env

# 2. Editar .env com seus valores
# (especialmente DB_PASSWORD e SECRET_KEY)

# 3. Subir todos os serviços
docker compose up -d

# 4. Verificar logs
docker compose logs -f
```

Serviços disponíveis:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Docs (Swagger): http://localhost:8000/docs
- MySQL: localhost:3306
- Redis: localhost:6379

## Como rodar localmente

### Backend

```bash
cd backend

# Criar e ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Copiar e configurar .env
cp ../.env.example .env

# Rodar servidor
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Rodar servidor de desenvolvimento
npm run dev
```

## Estrutura do projeto

```
ianalisys-saude/
├── backend/
│   └── app/
│       ├── api/v1/          # Rotas HTTP
│       ├── services/        # Lógica de negócio
│       ├── repositories/    # Acesso a dados
│       ├── models/          # Modelos SQLAlchemy
│       ├── schemas/         # Schemas Pydantic
│       ├── integrations/    # Clinicorp, Conta Azul
│       ├── analytics/       # Camada analytics
│       ├── ai/              # AI Gateway
│       ├── security/        # Auth, permissões
│       ├── tenants/         # Lógica multi-tenant
│       ├── workers/         # Tarefas assíncronas
│       ├── core/            # Config, settings
│       └── db/              # Session, base
├── frontend/
│   └── src/
│       ├── components/      # Componentes reutilizáveis
│       ├── pages/           # Páginas
│       ├── modules/         # Módulos por domínio
│       ├── services/        # Chamadas à API
│       ├── hooks/           # Custom hooks
│       ├── theme/           # Tema visual
│       └── types/           # Tipos TypeScript
├── docs/                    # Documentação do projeto
├── infra/                   # Configurações de infra
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```

## Documentação

> A pasta `docs/` é a **fonte de verdade** do projeto. Toda decisão de arquitetura, modelagem de dados, integrações e comportamento da IA está definida lá. Em caso de dúvida, consulte os documentos antes de implementar qualquer funcionalidade.

Consulte a pasta `docs/` para a documentação completa:

- [Visão do produto](docs/01_PRODUCT_VISION.md)
- [Arquitetura técnica](docs/02_ARCHITECTURE.md)
- [Modelo multi-tenant](docs/03_MULTI_TENANT_MODEL.md)
- [Modelo de dados](docs/04_DATABASE_MODEL.md)
- [Integrações](docs/05_API_INTEGRATIONS.md)
- [AI Gateway](docs/06_AI_GATEWAY.md)

## Verificar saúde da API

```bash
curl http://localhost:8000/api/v1/health
```
