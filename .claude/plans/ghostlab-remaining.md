# GhostLab Remaining Features — Implementation Plan

## Context

Проект TopInjector частично реализует функциональность GhostLab. Полная карта в `replica/architecture.md`. Этот план охватывает **всё что ещё не построено**, приоретизированное от критичных миграций к UI.

**Текущее состояние (2026-10-12):**
- Auth, проекты CRUD, очереди, аналитика (charts), проклик, группы/делегация/фильтры, настройки (messenger/external services) — ✅
- Миграции 0001/0002/0003 (batch_alter_table fix, inviter_user_id index) — ✅
- Backend: global-search, bulk-ops x4, auto-stop PUT/GET, report export CSV x2, avatar CRUD — ✅
- Frontend api.ts методы для всех новых эндпоинтов — ✅
- Multigeo UI, filter panel, mass edit toolbar, global search overlay, report export UI, avatar upload — ❌

---

## Phase 1: Missing Migrations ✅ COMPLETED

**Файлы:** `migrations/alembic/versions/`

### 1.1 Add columns (already in models but missing from migrations)
- `scheduling_window JSONB` on projects ✅
- `query_modifications JSONB` on projects  
- `query_modifications JSONB` on queries

### 1.2 New columns
- `auto_stop_at TIMESTAMPTZ` on projects (для auto-stop функции) ✅
- `avatar_url TEXT` on users (для avatar upload) ✅

### 1.3 Migration fixes for SQLite
- 0001_add_project_groups: batch_alter_table для FK на существующую колонку ✅
- 0002_add_project_delegates: добавлен inviter_user_id index, batch_alter_table в downgrade ✅

---

## Phase 2: Missing Backend API Endpoints ✅ COMPLETED

**Файлы:** `services/project_service/routes/projects.py`, `services/user_service/routes/users.py`

### 2.1 Global Search ✅ COMPLETED
- GET /api/global-search?q= — поиск по group.name, project.name/domain, query.text
- Возвращает {groups:[], projects:[], queries:[]} с href для навигации
- Endpoint в projects.py

### 2.2 Bulk Operations ✅ COMPLETED
- POST /projects/bulk-toggle — {project_ids[], is_active} ✅
- POST /projects/bulk-edit — {project_ids[], updates{}} (daily_limit, region, geo_settings...) ✅
- POST /projects/bulk-delete — {project_ids[]} (cascade) ✅
- POST /projects/bulk-delegate — {project_ids[], user_id, role} ✅

### 2.3 Report Export ✅ COMPLETED
- GET /api/projects/{id}/reports/analytics.csv — from_date/to_date params ✅
- GET /api/projects/{id}/reports/summary.csv — from_date/to_date params ✅

### 2.4 Auto-stop ✅ COMPLETED
- PUT /projects/{id}/auto-stop — {auto_stop_at} ✅
- GET /projects/{id}/auto-stop — current value ✅

### 2.5 Avatar ✅ COMPLETED
- POST /api/users/avatar — {avatar_url} ✅
- DELETE /api/users/avatar ✅
- GET /api/users/avatar ✅

---

## Phase 3: Model & Repository Updates

**Файлы:** `services/project_service/domain/models.py`, `services/project_service/repositories/project_repo.py`

### 3.1 Обновить Project модель — auto_stop_at если migration не покрывает
### 3.2 Обновить User модель — avatar_url если migration не покрывает  
### 3.3 new Repository methods: bulk operations, global_search

---

## Phase 4: Frontend — Listing Enhancements

**Файлы:** `frontend/src/routes/(app)/+page.svelte`, `api.ts`

### 4.1 Filter Panel — region / strategy / integration / access
- Выпадающая панель с фильтрами (расширение существующих filter states)
- Фильтр по интеграции: select из списка (default/test/main_bay_belarus)  
- Фильтр по доступу: own/delegated-to/delegated-by

### 4.2 Mass Edit Toolbar — checkbox selection → toolbar panel
- Панель появляется при selectedProjectIds > 0
- Кнопки: Start/Stop/Delegate/BulkEdit/AutoStop/Delete

### 4.3 Project Groups UI with Icons
- Модалка создания групп с выбором иконки (Lucide icons grid)
- Кликабельная ссылка на группу из project header → `/`?group_id=X

### 4.4 Bulk Edit Modal
- Массовое редактирование параметров для выбранных проектов
- Предупреждение "изменённые поля применяются ко всем"

---

## Phase 5: Multigeo UI

**Файлы:** `frontend/src/routes/(app)/+page.svelte` (create modal)

### 5.1 Multigeo Percentage Builder
- Секция в модалке создания/редактирования проекта
- Динамическое добавление регионов с % 
- Валидация сумма = 100%
- JSONB storage в geo_settings

### 5.2 Preset City Packs (placeholder)
- Dropdown с пресетами (Города-миллионники, Все города России...)
- Выбранные города → авто-добавление к мультигео

---

## Phase 6: Global Search Enhancement

**Файлы:** `frontend/src/routes/(app)/+layout.svelte`

### 6.1 Ctrl+E Overlay — результаты из /api/global-search
- Группировка результатов: группы/проекты/запросы
- Каждый результат — кликабельный (href navigation)

---

## Phase 7: Report Export UI

**Файлы:** `frontend/src/routes/(app)/analytics/+page.svelte`

### 7.1 Export Modal
- Кнопка "Экспорт" → модалка с date range + report type selection
- Скачивание CSV файла (blob URL)

---

## Phase 8: Settings — Avatar Upload

**Файлы:** `frontend/src/routes/(app)/settings/+page.svelte`

### 8.1 Avatar Section
- File input → preview → upload endpoint
- Remove button

---

## Phase 9: API Client (api.ts)

Добавить методы: globalSearch, bulkToggle, bulkEdit, bulkDelete, bulkDelegate, reportAnalytics, reportSummary, autoStop, uploadAvatar, deleteAvatar

---

## Verification

1. `alembic upgrade head` — all columns exist
2. Integration tests для новых endpoints
3. E2E: create project with multigeo → bulk-start 3 projects → global search → export analytics CSV → set auto-stop → avatar upload
