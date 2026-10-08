# TopInjector — Search Visibility Platform

SaaS platform for managing organic search visibility and traffic patterns. Helps SEO specialists coordinate click patterns, track position changes, and analyze traffic across multiple projects. Supports White Label reselling.

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd TopInjector

# Create environment
cp .env.example .env
# Edit .env with your settings

# Start infrastructure
docker compose up -d postgres redis rabbitmq

# Install backend dependencies
pip install uv && uv pip install -e ".[dev]"

# Run migrations (Alembic)
alembic upgrade head

# Start API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Architecture

**Modular Monolith** — single FastAPI process on port 8000 with clean module boundaries.

- `services/auth_service/` — JWT authentication
- `services/user_service/` — profiles & API tokens
- `services/project_service/` — project CRUD + query management
- `services/queue_service/` — task queue coordination
- `services/analytics_service/` — position tracking & traffic analysis
- `services/external_api_service/` — GhostLab-compatible REST API
- `services/notification_service/` — in-app notifications
- `core/` — shared utilities, config, database setup

## API Documentation

OpenAPI docs: http://localhost:8000/api/docs
ReDoc: http://localhost:8000/api/redoc

Full endpoint documentation: `API_DOCS.md`

## Frontend

Svelte 5 + SvelteKit + TypeScript + Tailwind CSS.

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

## Docker Deployment

```bash
docker compose up --build
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy async, Pydantic v2, JWT (python-jose), bcrypt
- **Frontend:** Svelte 5, SvelteKit, TypeScript, Tailwind CSS v3
- **Database:** PostgreSQL 16, Redis 7
- **Events:** RabbitMQ
- **Infra:** Docker Compose

## SOLID Principles

SRP, OCP (strategy pattern), LSP, ISP, DIP. Each service handles ONE business domain with narrow repository interfaces and clean layer separation.

## License

MIT
