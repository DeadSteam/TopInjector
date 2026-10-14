# GhostLab → TopInjector Architecture Map & Plan

**Source:** https://ghostlab.ru/docs/interface + sub-pages  
**Date:** 2026-10-12 (updated from recon dated 2026-10-10)  
**Platform:** Search traffic management panel — организация и контроль кликов по поисковым запросам в Яндексе

---

## 0. Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Web app | SvelteKit + TypeScript | Already in project (`frontend/`) |
| Styling | Tailwind CSS v3 (project CLAUDE.md) | Matches GhostLab design, primary `#3B82F6` |
| Backend | FastAPI microservices (Python) | Already built, multi-service architecture |
| Database | PostgreSQL 16 (Docker) | Core persistence per docker-compose |
| Cache/Sessions | Redis 7 | Caching + inter-service sessions |
| Messaging | RabbitMQ 3-management | Inter-service event bus + task queue |
| Worker | Celery | Queue task processing |
| ORM | SQLAlchemy async | Already in `shared/database/` |
| Auth | JWT (python-jose) + bcrypt | Existing auth service |
| API docs | Redocly OpenAPI | Already built at `/docs` |
| Hosting | Docker Compose (local) | Per project CLAUDE.md |

One database. No microservices for the clone — but TopInjector IS a microservice architecture, so we keep it as-is since services are already separated.

---

## 1. Screen Inventory & Status

### S01 Auth
| Item | GhostLab | Status |
|------|----------|--------|
| Email/password login | ✅ | Built |
| Forgot password | ✅ | Built (`/forgot-password`) |
| Registration | ✅ | Built (`/register`) |
| Cookie consent banner | ✅ | Built |

**Status: ✅ COMPLETE**

---

### S02 Projects Listing

#### Table Columns (all built)
| Column | Description | Status |
|--------|-------------|--------|
| Checkbox | Selection for bulk ops | ✅ Built |
| Activity toggle | Enable/disable project | ✅ Built |
| Name + group + delegate badge | Clickable group link, project name, delegation icons | ⚠️ Partial — badge UI skeleton only |
| Domain | Project site domain | ✅ Built |
| Region | Geo settings display | ✅ Built |
| Schedule type | daily/monthly/hourly | ✅ Built |
| Queries count | Total queries | ✅ Built |
| Plan/day | Scheduled clicks today | ✅ Built |
| Clicks done | Completed clicks count | ✅ Built |
| Queue | Pending tasks count | ✅ Built |
| Not found | Tasks where bot didn't find site | ✅ Built |
| Stuck | Tasks not completed in 10 min | ✅ Built |

#### Features
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Create project (+ button) | ✅ | ⚠️ Skeleton | Missing: integration selector, schedule window, full query-mods |
| Project groups (create, icons, assign) | ✅ | ⚠️ Skeleton | Model exists, no UI with icons |
| Group creation from listing | ✅ | ❌ Not built | |
| Import/Export projects (CSV) | ✅ | ⚠️ Skeleton | Backend endpoints exist per git log, frontend minimal |
| Filter: by group | ✅ | ❌ Not built | |
| Filter: by region | ✅ | ❌ Not built | |
| Filter: by activity | ✅ | Built toggle only | |
| Filter: by schedule type | ✅ | ❌ Not built | |
| Filter: by integration | ✅ | ❌ Not built | |
| Filter: by access (own/delegated-to/delegated-by) | ✅ | ❌ Not built | |
| Search: auto-search | ✅ | ⚠️ Partial | Basic name search exists |
| Global search (Ctrl+E): projects + queries | ✅ | ❌ Not built | Searches groups/projects/queries, opens filtered project |
| Column config (hide columns) | ✅ | ⚠️ Partial | Toggle for source breakdown columns only |
| Pagination settings | ✅ | Built — server-side pagination recently added (`feat/project-pagination`) |
| Overdue tasks toggle | ✅ | ✅ Built | Circles icon, filter pending tasks past scheduled time |
| Source breakdown (strategy/autoburst/proklik) | ✅ | ✅ Built | Toggle + columns per source |
| Mass edit toolbar (start/stop/delegate/bulk-edit/auto-stop/delete) | ✅ | ❌ Not built | Checkbox selection → bulk actions panel |
| Context menu 3-dots (edit/copy/auto-stop/delete) | ✅ | ⚠️ Partial | Right-click menu built: Open/Edit/Start-Stop/Copy/Delete |
| Copy project (settings only / full with queries) | ✅ | ✅ Built | Backend `POST /projects/{id}/copy` |

**Status: ⚠️ PARTIAL — Core table and columns work. Missing: filters panel, global search, mass edit toolbar, group UI.**

---

### S03 Create/Edit Project

#### Fields
| Field | Description | Status |
|-------|-------------|--------|
| Group | Assign to project group | ⚠️ Skeleton — no UI with icons |
| Name | Project name | ✅ Built |
| Domain | Website domain | ✅ Built |
| Integration | Bot pool (Int 2 / Int 1 test / Main Bay Belarus) | ⚠️ Partial — stored but no selector UI |
| Schedule type | daily/monthly/hourly | ✅ Built |
| Daily click limit | Upper bound | ✅ Built |
| Schedule window | Time range (e.g. 7:00-22:00) | ✅ Built — time pickers stored as JSON |
| Geo settings | Full multigeo system | ⚠️ Partial — JSON column exists, no multigeo UI |
| Suggestions (line-by-line) | Search hints before query | ✅ Built — text area input |
| Query modifications | capital_first/random_caps/typos/trailing_space | ✅ Built — JSON flags + modal UI |

#### Geo System
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Specific cities (search by name or Yandex code) | ✅ | ❌ Not built | Need city database |
| Preset city packs (millions, all Russia, Moscow Oblast, etc.) | ✅ | ❌ Not built | Need Yandex geo codes DB |
| Multigeo with percentage distribution | ✅ | ❌ Not built | e.g. Moscow 45%, Millions 20% |
| Custom Yandex code entry | ✅ | ❌ Not built | |

#### Boost Tab
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Boost time window | Schedule for autobursts | ✅ Built — time pickers |
| Day distribution | Mon-Sun checkboxes | ✅ Built |
| Boost from project detail | Select queries → Boost → count+interval → redistribute now/tomorrow | ✅ Built |

**Status: ⚠️ PARTIAL — Basic fields work. Missing: full integration selector, multigeo UI, preset city packs, schedule window UI (partially done).**

---

### S04 Project Detail Page

#### Header
| Feature | GhostLab | Status |
|---------|----------|--------|
| Clickable group name → filter | ✅ | ❌ Not built |
| Activity toggle | ✅ | Built as column action |
| Edit settings button | ✅ | ⚠️ Partial — Settings tab on project detail |

#### Actions Menu (3 dots)
| Action | GhostLab | Status | Notes |
|--------|----------|--------|-------|
| Copy project | ✅ | ✅ Built | Settings only / full with queries |
| Delegate project | ✅ | ⚠️ Partial — model exists, UI minimal | With view/edit roles |
| Auto-stop (date/time) | ✅ | Built endpoint, UI needed | Stops project at given time |
| Clear queue | ✅ | ✅ Built | `POST /projects/{id}/clear-queue` |
| Collect frequency (XML River) | ✅ | ⚠️ Needs XML config | Requires UserID + APK set in settings |
| Delete project | ✅ | ✅ Built |

#### Instant Click (Проклик)
| Mode | GhostLab | Status | Notes |
|------|----------|--------|-------|
| Random count (1 to total) | ✅ | ✅ Built | Modal with count input |
| Per-query: 1 click each | ✅ | ✅ Built | |
| Per-query: equals daily clicks | ✅ | ✅ Built | |
| Manual value per query | ✅ | ✅ Built | |
| Random range | ✅ | ✅ Built | |

#### Per-Query Edit Modal (Mini-modal)
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Geo override per query | ✅ | ⚠️ Partial — JSON column exists, UI in inline edit | Individual geo separate from project |
| Change daily clicks (hard / % of frequency) | ✅ | Built — quick +/- and full edit modal | 3% = ~100% CTR logic |
| Apply click URL | ✅ | Built — click_url field with toggle | Instead of project default URL |
| Delete queries | ✅ | ✅ Built — bulk delete selected |

#### Info Panel
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Strategy stats + limits | ✅ | ✅ Built | Current schedule/limits display |
| Clicks by source breakdown | ✅ | ✅ Built | Strategy/autoburst/proklik counts |
| Queue status summary | ✅ | ✅ Built | pending/in_progress/completed/not_found/stuck |
| Quick links to queue/analytics | ✅ | ✅ Built | Direct nav + preset filters |

#### Query Table Columns
| Column | Description | Status |
|--------|-------------|--------|
| Text query | Search query text | ✅ Built |
| URL (target) | Target URL — editable inline with confirm | ✅ Built |
| Click URL | Bot's most frequent click URL — copy/transfer | ✅ Built |
| Geo | Individual override vs project geo | ⚠️ Partial — JSON column exists |
| Daily clicks | Inline-editable quick +/- | ✅ Built |
| Avg position | From analytics — bot click positions | ✅ Built |
| Clicks today | Per-query daily count | ✅ Built |
| Autoburst settings | Editable in browser | ✅ Built |
| Frequency | Collected via XML River | ⚠️ Partial — DB column exists |

#### Query Filters
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Position range (e.g. 2nd to 10th) | ✅ | ✅ Built | Range filter in panel |
| Frequency range (min) | ✅ | ✅ Built | Min frequency filter |
| Text search on query | ✅ | ✅ Built | Search by text |

#### Notifications Bell
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Project updates, proklik send/delete/clear queue | ✅ | Built — bell icon exists | Notification service integrated |

**Status: ⚠️ PARTIAL — Core table, proklik, info panel built. Missing: clickable group link in header, geo override UI, full filter panel.**

---

### S05 Analytics Page

#### Report Export
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Full analytics report | ✅ | ❌ Not built | All data export |
| Summary report (user/project/domain/geo/clicks/URL/position) | ✅ | ❌ Not built | Selected projects + date range |

#### Filters
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Period (custom date range) | ✅ | Built — date picker exists | |
| Projects (select specific) | ✅ | Built — filter exists | |
| Query text search | ✅ | Built | |
| Geo filter | ✅ | Built | Shows cities with clicks for multigeo |
| Suggestion mode (all / with-only / without-suggestions) | ✅ | ⚠️ Partial — needs UI toggle | All = includes pos 1 clicks |
| Avg position threshold | ✅ | ⚠️ Partial — needs filter input | e.g. show queries beyond TOP-10 |

#### Charts
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Clicks in TOP ranges chart (TOP-3,5,10 etc) | ✅ | ✅ Built — SVG horizontal bars + timeline | `feat/analytics-charts` added |
| Avg position by range | ✅ | ✅ Built — alongside TOP ranges | Toggleable off |
| Timeline bar chart | ✅ | ✅ Built — daily clicks timeline | Clickable for drill-down |
| Position tracking line chart | ✅ | ✅ Built — SVG line overlay | |

#### Analytics Table
| Column | Description | Status |
|--------|-------------|--------|
| Query (clickable → project filtered) | ✅ | ✅ Built |
| Strategy clicks | Scheduled clicks count | ✅ Built |
| Config URL | Click target from settings | ✅ Built |
| Actual click URL (toggleable display) | Bot's most frequent click | ✅ Built — toggle view |
| Clicks in period | Total for selected range | ✅ Built |
| Avg position | For period | ✅ Built |
| Daily breakdown (clicks + position per day) | Per-day stats table cell | ⚠️ Partial — daily count shown, full drill-down modal needed |

#### Daily Drill-Down Modal (click "i" on day cell)
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Geo of each click | ✅ | ✅ Built in drill-down | |
| Source per click (strategy/autoburst/proklik) | ✅ | ✅ Built | |
| Position at time of click | ✅ | ✅ Built | |
| Click timestamp | ✅ | ✅ Built | |
| URL clicked | ✅ | ✅ Built | |
| Geo + suggestion filters | ✅ | ⚠️ Partial — needs filter UI in modal | |
| Summary: total / without-suggestions / with-suggestions | ✅ | ✅ Built | |
| Not-found count | ✅ | Built | Tasks where click wasn't completed |

#### Inline Edit from Analytics
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Edit daily clicks per project (with confirm) | ✅ | ✅ Built — preset amounts + custom input | `feat/analytics-inline-edit` added |

**Status: ⚠️ PARTIAL — Charts and core table built. Missing: report export, suggestion mode filter, position threshold filter, full drill-down modal filters.**

---

### S06 Queue Page

#### Filters
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Status (in-queue / in-progress / completed / not-found / stuck) | ✅ | ✅ Built | |
| Source (strategy / autoburst / proklik) | ✅ | ✅ Built | |
| Project (specific project filter) | ✅ | ⚠️ Partial — needs filter input | |
| Time range (e.g. next hour) | ✅ | ⚠️ Partial — needs date range picker | |
| Text search on query | ✅ | ⚠️ Partial — exists but may need enhancement | |

#### Task Detail Modal
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Queue set time | ✅ | ✅ Built | |
| Status | ✅ | ✅ Built | |
| Source | ✅ | ✅ Built | |
| Click URL | ✅ | ✅ Built | |

#### Clear Queue with Filters
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Clear tasks respecting active filters | ✅ | ✅ Built | Delete tasks matching status/source/project/time |

**Status: ⚠️ PARTIAL — Core filters and task detail built. Missing: project filter UI, time range picker, enhanced text search.**

---

### S07 Status Bar (Dashborad)

| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Overdue tasks counter (red badge > 0) | ✅ | ⚠️ Partial — backend exists, UI in header | Tasks whose scheduled time passed |
| Clicks today: planned vs completed | ✅ | ✅ Built — progress display | ~50% expected midday |
| Notifications bell | ✅ | ✅ Built | With events |
| Balance display | ✅ | ⚠️ Partial — placeholder, real balance table missing | Account credit system |

**Status: ⚠️ PARTIAL — All elements displayed. Missing: real balance integration.**

---

### S08 Settings / Profile

#### Profile
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| Avatar upload | ✅ | ❌ Not built | |
| First name + last name | ✅ | Built — editable | Recommended for identification |
| Password change | ✅ | ✅ Built | Current password verification → bcrypt hash |
| Messengers: Telegram webhook URL | ✅ | ✅ Built | For notifications |
| Messengers: Max Connector ID | ✅ | ✅ Built | |
| API key | ✅ | ⚠️ Partial — stored, display needed | For external integrations |

#### External Services
| Feature | GhostLab | Status | Notes |
|---------|----------|--------|-------|
| XML River (UserID + APK for frequency) | ✅ | ✅ Built | Stored as JSON in user settings |
| XMLStock (multiple API keys) | ✅ | ✅ Built | Dynamic entries with name/api_key |

#### Glossary (Terms Reference Table)
| Term | GhostLab Definition |
|------|---------------------|
| Стратегия | Основной план распределения кликов (daily/monthly/hourly) |
| Автобуст | Дополнительные клики параллельно стратегии с фиксированным интервалом |
| Проклик | Мгновенная ручная отправка задач |
| Интеграция | Набор ботов с настройками для выполнения задач |
| Подсказка | Текст, вводимый ботом перед основным запросом |
| Не найдено | Бот не нашёл сайт в выдаче, клик не выполнен |
| Зависшая задача | Задача в работе более 10 минут без результата |
| Делегирование | Передача доступа проекту другому пользователю |
| Лимит кликов | Верхняя граница кликов в сутки по проекту |
| URL клика | Частотный URL, по которому боты фактически кликают |
| Мультигео | Распределение по регионам с процентовкой |
| Автостоп | Авто-остановка проекта в дату/время |

**Status: ⚠️ PARTIAL — Core settings built. Missing: avatar upload, API key display management.**

---

### S09 API Docs
| Feature | Status | Notes |
|---------|--------|-------|
| Redocly OpenAPI at /docs | ✅ Built | Loads spec from `/api/internal/openapi.json` with fallback |

**Status: ✅ COMPLETE**

---

## 2. Database Schema

### Already Existing (per current codebase)
- `projects` — id, name, domain, geo_settings JSON, integrations JSON, schedule_type, daily_limit, scheduling_window JSON, query_modifications JSON, created_by FK → users, created_at, updated_at
- `project_groups` — id, name, icon, created_by FK → users, created_at
- `project_delegate` — id, project_id FK, user_id FK, role, created_at
- `queries` — id, project_id FK, text, url (target), click_url, geo JSON, daily_clicks, position, boost_min/max, frequency, query_modifications JSON, created_at
- `queue_tasks` — id, project_id FK, query_id FK, source (strategy/autoburst/proklik), status (pending/in_progress/completed/not_found/stuck), click_url, position, scheduled_time, created_at, completed_at
- `analytics_clicks` — interaction event records with geo, source, position, timestamp, url
- `user_settings` — messenger (telegram_webhook_url, max_connector_id), external_services (xml_river, xml_stock)
- `project_tokens` — for mobile client auth
- `balance_transactions` — project credit tracking

### Missing Tables Needed
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `notifications` | In-app notifications | user_id FK, type, title, body, read Boolean, created_at |
| `project_audit_log` | Audit trail for changes | project_id FK, user_id FK, action, old_values JSON, new_values JSON, created_at |

### Missing Columns Needed
| Table | Column | Purpose |
|-------|--------|---------|
| `projects` | `auto_stop_at timestamptz` | Auto-stop date/time setting |
| `projects` | `is_active Boolean DEFAULT true` | Project activation state (currently implicit) |
| `queries` | `suggestions JSONB` | Per-query suggestion overrides |
| `users` | `avatar_url text` | Avatar storage |

---

## 3. API Routes Map

### Already Built (per API_DOCS.md + git log)
```
POST   /api/auth/login
POST   /api/auth/register
POST   /api/auth/logout
GET    /api/users/me
PUT    /api/users/me

POST   /api/projects                          # create
GET    /api/projects                          # list (paginated)
GET    /api/projects/{id}                     # detail
PUT    /api/projects/{id}                     # update
DELETE /api/projects/{id}                     # delete
POST   /api/projects/{id}/copy                # duplicate project
POST   /api/projects/{id}/activate            # toggle active
POST   /api/projects/{id}/clear-queue         # clear tasks
GET    /api/projects/{id}/clicks              # click stats
GET    /api/projects/{id}/source-breakdown    # by source counts
GET    /api/projects/{id}/overdue-count       # overdue pending tasks

POST   /api/projects/{project_id}/queries/import    # bulk import CSV
POST   /api/projects/{project_id}/queries/export    # bulk export CSV
POST   /api/projects/{project_id}/queries/bulk-update  # update selected queries
POST   /api/projects/{project_id}/queries/bulk-delete    # delete selected queries

POST   /api/boost                              # create autoburst schedule
GET    /api/boost                              # list boost schedules

GET    /api/queue/dashboard-stats              # overdue + today planned/completed
GET    /api/queue/tasks                        # task list (paginated)
DELETE /api/queue/tasks/clear                  # clear with filters

POST   /api/analytics/clicks                   # record interaction event
GET    /api/analytics/summary                  # analytics summary
GET    /api/analytics/daily                    # daily drill-down data

GET    /api/settings/messenger                 # get messenger settings
PUT    /api/settings/messenger                 # update messenger settings
GET    /api/settings/external-services         # get external services
PUT    /api/settings/external-services         # update external services
POST   /api/password                           # change password

POST   /api/external/v1/projects               # create project (from mobile)
PUT    /api/external/v1/projects/{id}          # update project (mobile)
POST   /api/external/v1/terms/upsert           # bulk upsert queries (mobile)
POST   /api/external/v1/queue/push             # add tasks to queue (mobile)
POST   /api/external/v1/queue/results          # submit results (mobile)
POST   /api/external/v1/users                  # invite user (mobile)
POST   /api/external/v1/balance/add            # add credit (mobile)
POST   /api/external/v1/balance/set            # set credit (mobile)
GET    /api/external/v1/health                 # health check

GET    /api/internal/openapi.json              # OpenAPI spec for Redocly
```

### Missing API Routes Needed
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/projects/groups` | List all user's project groups |
| POST | `/api/projects/groups` | Create project group |
| PUT | `/api/projects/groups/{id}` | Update project group (name, icon) |
| DELETE | `/api/projects/groups/{id}` | Delete project group |
| GET | `/api/global-search` | Search across groups, projects, queries |
| POST | `/api/projects/bulk-edit` | Mass edit multiple projects |
| POST | `/api/projects/bulk-toggle` | Start/stop multiple projects |
| POST | `/api/projects/bulk-delete` | Delete multiple projects |
| POST | `/api/projects/bulk-delegate` | Delegate multiple projects |
| GET | `/api/reports/analytics` | Export full analytics report (CSV) |
| POST | `/api/reports/summary` | Generate summary report |
| PUT | `/api/projects/{id}/auto-stop` | Set auto-stop date/time |
| GET | `/api/city-presets` | Preset city packs for geo selection |
| GET | `/api/geocodes/search?q=` | Search cities by name or code |
| POST | `/api/users/avatar/upload` | Upload user avatar |
| GET | `/api/notifications` | List user notifications |
| PUT | `/api/notifications/{id}/read` | Mark notification as read |

---

## 4. Frontend Pages Map

### Already Built (per SvelteKit routes)
- `/login` — sign in form
- `/` — project listing table with server-side pagination, filters (overdue toggle, source breakdown)
- `/projects/{id}` — project detail page with Queries tab, Queue tab, Analytics tab, Positions/Maker/Webmarker tabs
- `/analytics` — analytics dashboard with TOP charts, timeline, daily drill-down modal
- `/queue` — real-time task monitoring with status/source filters, task detail modal
- `/settings` — profile + messengers + external services + password settings

### Missing Frontend Pages/Components
| Component | Purpose | Priority |
|-----------|---------|----------|
| Project Groups UI (create/edit/list) | Group management with icons | High |
| Filter panel on listing (group/region/strategy/integration/access) | Multi-criteria filtering | High |
| Global search overlay (Ctrl+E) | System-wide search across projects+queries | High |
| Mass edit toolbar | Appears when multiple projects selected | High |
| Multigeo configuration UI | Percentage-based region distribution | High |
| Preset city packs selector | Browse/select city groups | Medium |
| Geo code search input | Type-ahead for Yandex codes | Medium |
| Project header group link | Clickable group name navigating to filter | Medium |
| Report export UI (full + summary) | Date range → download CSV | Medium |
| Analytics drill-down modal filters | Geo + suggestion filters inside modal | Low |
| User avatar upload | Image upload with preview | Low |
| Balance management page | Top-up history, transaction log | Low |

---

## 5. Build Order

### Milestone 1: Vertical Slice — Complete the Core Loop
**Goal:** Create project → Add queries → See clicks in analytics end-to-end with full UI polish.

1. **Project Groups UI** — create/edit/delete groups with icons, assign projects to groups from listing modal
2. **Listing Filter Panel** — add filter panel for group, region, strategy, integration, access; integrate with existing query params
3. **Global Search (Ctrl+E)** — overlay component hitting `/api/global-search`, results showing groups/projects/queries with navigation
4. **Geo Settings UI** — multigeo percentage builder, preset city packs dropdown, Yandex code search input

### Milestone 2: Must-Haves from features.csv
5. **Mass Edit Toolbar** — checkbox selection on listing → toolbar with start/stop/delegate/bulk-edit/auto-stop/delete
6. **Enhanced Project Create/Edit** — full integration selector UI, schedule window visual picker (enhancement), multigeo save/load
7. **Project Header Enhancement** — clickable group name in header → navigates to filtered listing, view settings button
8. **Delegation UI** — invite user flow, role selection (view/edit), delegation badge management, incoming/outgoing delegation tables
9. **Report Export** — analytics page export buttons for full/summary reports with date range picker
10. **Drill-Down Modal Filters** — geo and suggestion mode filters inside daily drill-down modal

### Milestone 3: Should-Haves
11. **Avatar Upload** — file input, preview, server-side resize/upload
12. **Balance Management** — balance detail page, transaction history table, top-up form (for self-serve)
13. **API Key Management** — regenerate/display API key in settings
14. **Notifications Page** — full notification center with read/unread states, filter by type
15. **Auto-Stop UI** — set/cancel auto-stop date-time from project detail and context menu

### Milestone 4: Polish + Edge Cases
16. **CSV Import/Export Enhancements** — format validation, error reporting, column mapping UI
17. **Audit Log View** — browse project changes with timestamps and actor
18. **Preset City Packs** — populate city code database (Yandex geo codes), build selector UI
19. **Performance Optimization** — listing page query optimization for source breakdown aggregation, global search index tuning

---

## 6. The Parts That Bite

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Time zones & DST | Schedule window + auto_stop_at must handle UTC consistently | Store all timestamptz in DB, convert to local only on frontend display |
| Race conditions (queue workers) | Multiple workers grabbing same task | Use `UPDATE ... WHERE status='pending' RETURNING id` for task claiming |
| Rate limits (mobile clients) | External API rate limit per project token | Redis sliding window counter, return 429 with retry-after |
| CSV import/export volume | Large query sets (10k+ rows) | Stream processing, async job with status polling |
| File size limits | Avatar upload, CSV import | Max 5MB avatar, server-side validation on import |
| Multigeo percentage sum | Must always equal 100% | Frontend validation + backend check constraint |
| Search performance | Global search across queries (large table) | Full-text index on `queries.text` with tsvector, project prefix filter |
| Notification delivery | Telegram webhook failures | Retry queue via Celery, dead letter for failed webhooks |
| Balance consistency | Concurrent add/set operations | Database transactions with row-level locking on balance records |

---

## 7. Riskiest Parts

1. **Multigeo system** — percentage-based region distribution with preset packs requires a city code database and careful percentage validation
2. **Global search** — full-text search across projects + queries with result type distinction needs tsvector indexes
3. **Queue task claiming** — race condition between Celery workers on task assignment; must use atomic UPDATE...RETURNING

---

## 6. Next Step

`/replica-design` — design system mapping and UI component library for the remaining screens.
