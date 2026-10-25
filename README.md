# TopInjector — Search Visibility Platform

SaaS platform for managing organic search visibility and traffic patterns. Helps SEO specialists coordinate click patterns, track position changes, and analyze traffic across multiple projects. Supports White Label reselling.

## Quick Start

Python dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`, Python 3.12).

```bash
git clone <repo>
cd TopInjector

# Infrastructure (Postgres on :5433, Redis on :6380)
docker compose up -d postgres redis rabbitmq

# Backend: creates .venv from uv.lock, including dev tools (pytest, ruff)
uv sync

# .env for local runs against the containers above (see "Configuration")
#   POSTGRES_PORT=5433
#   REDIS_PORT=6380

uv run alembic upgrade head
uv run uvicorn main:app --reload --port 8000

# Frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev    # http://localhost:5173
```

Tests and lint:

```bash
uv run pytest
uv run ruff check .
```

Adding a dependency: `uv add <package>` (or `uv add --dev <package>`), then commit `uv.lock`.

## Configuration

Settings come from environment variables or `.env` (`shared/config/settings.py`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `localhost` / `5432` / `ghostlab` / `ghostlab_pass` / `ghostlab` | Database (or `DATABASE_URL`) |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Redis; Celery uses DBs 10 and 11 |
| `JWT_SECRET` | dev placeholder | **Set a long random value in production** |
| `FRONTEND_URL` | `http://localhost:5173` | Base of links in verification e-mails |
| `ADMIN_EMAILS` | empty | Comma-separated e-mails that see the admin panel |
| `SCHEDULE_TIMEZONE` | `Europe/Moscow` | Timezone of project scheduling windows and daily quotas |
| `SMTP_*`, `EMAIL_ENABLED` | off | Outgoing e-mail |

## Architecture

**Modular Monolith** — single FastAPI process on port 8000 with clean module boundaries.

- `services/auth_service/` — JWT authentication
- `services/user_service/` — profiles & API tokens
- `services/project_service/` — project CRUD + query management
- `services/queue_service/` — task queue coordination
- `services/analytics_service/` — position tracking & traffic analysis
- `services/external_api_service/` — GhostLab-compatible REST API
- `services/notification_service/` — in-app notifications
- `shared/` — config, database, auth and access control, validation helpers
- `workers/` — Celery tasks: strategy scheduler (every minute), stale-task checker (every 10 min)

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
docker compose up -d --build
# Everything behind nginx: http://localhost:8082 (UI), http://localhost:8082/api/... (API)
# OpenAPI docs: http://localhost:8082/api/docs
```

The `api` container runs uvicorn, the Celery worker and Celery beat under supervisord and applies Alembic migrations on start.

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
