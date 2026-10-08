# TopInjector — Полная документация по API эндпоинтам

## Архитектура модулей (Modular Monolith)

Все сервисы работают в одном FastAPI процессе на порту 8000. Границы модулей:

```
/auth/          → Auth module (login, register, JWT tokens)
/users/         → User module (profile, API tokens)
/projects/      → Project module (CRUD projects, queries/terms)
/queue/         → Queue module (push tasks, submit results, list status)
/analytics/     → Analytics module (positions, clicks, summary)
/notifications/ → Notification module (user notifications)
/api/external/v1/ → External API (GhostLab-compatible)
```

---

## 1. Auth Module (`/api/auth/`)

### POST `/api/auth/register`
**Request:** `{ "email": "user@example.com", "password": "secret123", "display_name": "User" }`
**Response 200:** `{ "access_token": "...", "refresh_token": "...", "token_type": "Bearer" }`
**Response 409:** `{ "detail": "Email already registered" }`

### POST `/api/auth/login`
**Request:** `{ "email": "user@example.com", "password": "secret123" }`
**Response 200:** `{ "access_token": "...", "refresh_token": "...", "token_type": "Bearer" }`
**Response 401:** `{ "detail": "Invalid credentials" }`

### POST `/api/auth/refresh`
**Request:** `{ "refresh_token": "..." }`
**Response 200:** `{ "access_token": "...", "refresh_token": "...", "token_type": "Bearer" }`
**Response 401:** `{ "detail": "Invalid refresh token" }`

### GET `/api/auth/me`
**Headers:** `Authorization: Bearer <token>`
**Response 200:** `{ "user_id": "uuid", "token_type": "access" }`

---

## 2. Projects Module (`/api/projects/`)

### POST `/api/projects/`
**Request:** `{ "name": "MySite", "domain": "mysite.ru", "strategy_type": "daily", "daily_limit": 500, "region": "moscow" }`
**Response 200:** `{ "id": "uuid", "name": "MySite", "domain": "mysite.ru" }`

### GET `/api/projects/`
**Response 200:** `[{ "id": "uuid", "name": "...", "domain": "...", "strategy_type": "...", "daily_limit": 500, "is_active": true }]`

### GET `/api/projects/{id}`
**Response 200:** `{ "id": "...", "name": "...", "domain": "...", "strategy_type": "...", "daily_limit": 500, "region": "...", "is_active": true }`
**Response 404:** `{ "detail": "Project not found" }`

### PUT `/api/projects/{id}`
**Request:** `{ "name": "NewName", "daily_limit": 1000 }`
**Response 200:** `{ "id": "...", "updated": true }`

### DELETE `/api/projects/{id}`
**Response 200:** `{ "deleted": true }`

---

## 3. Queries/Terms Module (`/api/projects/{project_id}/queries`)

### POST `/api/projects/{project_id}/queries`
**Request:** `{ "text": "купить слона", "url": "https://mysite.ru/slon", "click_url": "http://yandex.ru/search?q=купить+слона" }`
**Response 200:** `{ "id": "uuid", "text": "купить слона" }`

### GET `/api/projects/{project_id}/queries`
**Response 200:** `[{ "id": "...", "text": "...", "url": "...", "click_url": "...", "geo": null, "daily_clicks": 0 }]`

---

## 4. Queue Module (`/api/queue/`)

### POST `/api/queue/push`
**Request:** `{ "project_id": "...", "tasks": [{ "query_id": "...", "click_url": "http://yandex.ru/...", "source": "strategy", "geo": { "city": "moscow" } }] }`
**Response 200:** `{ "queued": 10, "already_exists": 0 }`

### GET `/api/queue/`
**Query params:** `?project_id=xxx&status=pending`
**Response 200:** `[{ "id": "...", "status": "pending", "source": "strategy", "click_url": "...", "geo": {...}, "created_at": "2024-01-01T00:00:00Z" }]`

### POST `/api/queue/results`
**Request:** `{ "results": [{ "task_id": "...", "status": "completed", "position": 5 }] }`
**Response 200:** `{ "updated": 1, "errors": [] }`

### POST `/api/queue/clear`
**Query params:** `?project_id=xxx`
**Response 200:** `{ "deleted": 5 }`

---

## 5. Analytics Module (`/api/analytics/`)

### GET `/api/analytics/positions`
**Response 200:** `{ "positions": [], "total": 0 }` — Tracking data with position history and direction (up/down/stable)

### GET `/api/analytics/clicks`
**Response 200:** `{ "clicks": [], "total": 0 }` — Clicks grouped by date, geo, source with summary stats

### GET `/api/analytics/summary`
**Response 200:** `{ "total_clicks": 0, "completed_rate": 0.0, "avg_position": 0, "projects_active": 0 }` — High-level summary

---

## 6. External API (`/api/external/v1/`)

Auth via `X-Auth-Token` header (API key from /api/users/api-tokens)

### POST `/api/external/v1/projects`
**Request:** `{ "name": "...", "domain": "...", "strategy_type": "daily", "daily_limit": 500 }`
**Response 200:** `{ ...project data with id }`

### GET `/api/external/v1/projects`
**Response 200:** `[ { "id": "...", "name": "...", "domain": "..." } ]`

### PUT `/api/external/v1/projects/{id}`
**Request:** `{ "name": "NewName" }`
**Response 200:** Updated project

### PATCH `/api/external/v1/projects/{id}/status`
**Request:** `{ "is_active": true }`
**Response 200:** Updated project

### DELETE `/api/external/v1/projects/{id}`
**Response 200:** `{ "deleted": true }`

### POST `/api/external/v1/terms/upsert`
**Request:** `{ "project_id": "...", "terms": [{ "text": "query" }] }`
**Response 200:** `{ "created": 10, "updated": 5, "deleted": 0 }`

### GET `/api/external/v1/terms?project_id=xxx`
**Response 200:** `{ "terms": [...], "total": N }`

### POST `/api/external/v1/queue/push`
**Request:** `{ "project_id": "...", "tasks": [{ "query_id": "...", "click_url": "..." }] }`
**Response 200:** `{ "queued": 5, "already_exists": 0 }`

### GET `/api/external/v1/queue?project_id=xxx&status=pending`
**Response 200:** `{ "tasks": [...], "total": N }`

### POST `/api/external/v1/queue/clear`
**Request:** `{ "project_id": "..." }`
**Response 200:** `{ "deleted": N }`

### POST `/api/external/v1/queue/results`
**Request:** `{ "results": [{ "task_id": "...", "status": "completed" }] }`
**Response 200:** `{ "updated": N, "errors": [] }`

### POST `/api/external/v1/users`
**Request:** `{ "email": "...", "display_name": "...", "role": "user" }`
**Response 200:** `{ ...user data with id and balance }`

### GET `/api/external/v1/users`
**Response 200:** `[ { "id": "...", "email": "...", "balance": 0 } ]`

### PUT `/api/external/v1/users/{id}` (Auth: X-Auth-Token)
**Request:** `{ "display_name": "NewName" }`
**Response 200:** Updated user

### PATCH `/api/external/v1/users/{id}/status` (Auth: X-Auth-Token)
**Request:** `{ "is_active": true }`
**Response 200:** Updated user

### POST `/api/external/v1/balance/add` (Auth: X-Auth-Token)
**Request:** `{ "user_id": "...", "amount": 100 }`
**Response 200:** `{ "user_id": "...", "balance": 500, "added": 100 }`

### POST `/api/external/v1/balance/set` (Auth: X-Auth-Token)
**Request:** `{ "user_id": "...", "amount": 500 }`
**Response 200:** `{ "user_id": "...", "balance": 500 }`

### GET `/api/external/v1/project-groups`
**Response 200:** `[ { "id": "...", "name": "...", "project_count": 0 } ]`

### GET `/api/external/v1/boosts?project_id=xxx`
**Response 200:** `[ { "id": "...", "name": "...", "interval_minutes": 180, "is_active": true } ]`

---

## 7. User Module (`/api/users/`)

### GET `/api/users/profile`
**Response 200:** `{ "id": "...", "email": "...", "display_name": "...", "balance": 0, "plan": "free" }`

### PUT `/api/users/profile`
**Request:** `{ "display_name": "NewName" }`
**Response 200:** Updated profile

### GET `/api/users/api-tokens`
**Response 200:** `[ { "id": "...", "name": "Main", "token": "tl_..." } ]`

### POST `/api/users/api-tokens`
**Request:** `{ "name": "New Token" }`
**Response 200:** `{ "id": "...", "name": "...", "token": "tl_..." }`

---

## Бизнес-логика и сервисный слой

### Жизненный цикл задачи (Task Lifecycle):
1. **pending** — задача создана, ожидает своей очереди
2. **in_progress** — задача забрана воркером для обработки
3. **completed** — клик выполнен успешно
4. **not_found** — URL не найден в выдаче
5. **stuck** — задача зависла (>10 минут в in_progress)

### Стратегии распределения:
- **daily** — равномерное распределение лимита на 24 часа (00:00-23:59)
- **monthly** — распределение по 30 дням с учётом выходных
- **hourly** — точный лимит по каждому часу

### Источники задач (source):
- **strategy** — основная стратегия расписания проекта
- **autoburst** — параллельные автобусты с фиксированным интервалом
- **proklik** — мгновенная задача из ручной отправки

### Geo настройка:
Geo задается в формате JSON: `{"city": "moscow", "region_code": 50}`
Поддерживается мультигео: `{"cities": [{"city": "moscow", "percent": 60}, {"city": "spb", "percent": 40}]}`
