# Action Plan — Next Session (TopInjector)

## Current State
- ✅ FastAPI modular monolith with basic CRUD routes
- ✅ SvelteKit frontend with login/projects/analytics/queue/settings pages
- ✅ Docker Compose for infra (postgres, redis, rabbitmq)
- ❌ Duplicate service directories (auth-service vs auth_service)
- ❌ Model ID mismatch: Project.user_id=Integer but User.id=UUID
- ❌ No auth dependency on protected routes
- ❌ External API doesn't validate X-Auth-Token against DB

## Priority Order

### 1. Clean up duplicates (30min)
Delete old hyphen dirs, keep underscore-only structure

### 2. Fix model FK (15min)
Update Project.user_id from Integer to String(36) for UUID compatibility

### 3. Alembic migrations (45min)
Create alembic.ini + env.py + generate initial migration

### 4. Auth dependency (1h)
Add get_current_user() middleware, apply to all protected routes

### 5. External API token validation (1h)
Implement ProjectToken lookup in external API routes

### 6. Repository/service layer (2h)
Abstract raw SQL → repository interfaces + service business logic

### 7. Celery workers (3h)
Queue scheduler + stuck task checker

### 8. Frontend auth flow (1h)
Fix api.ts to send JWT headers, add register page

### 9. Tests (2h)
Auth, projects, external API endpoints
