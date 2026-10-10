# Build Log — GhostLab Replica

## S02 Listing Enhancements
**Date:** 2026-10-10
**Status:** Built
**Done:**
- Source breakdown checkbox toggle — shows/hides columns for completed clicks by source (strategy/autoburst/proklik)
- Overdue toggle — filters projects that have pending tasks past their scheduled time
- Backend endpoints: `/api/projects/{id}/source-breakdown`, `/api/projects/{id}/overdue-count`

**Harder than expected:** Fetching source breakdown per project requires batch API calls. Using Promise.allSettled for resilience. The listing page had to be updated to re-fetch breakdown data after CRUD operations.

## S07 Status Bar
**Date:** 2026-10-10
**Status:** Built
**Done:**
- Dashboard stats endpoint: `GET /api/queue/dashboard-stats` — aggregates overdue count, today's planned/completed clicks, balance across all user projects
- Thin status bar in layout header above all page content
- Shows: overdue counter (red badge when >0), today clicks progress (completed/plan), balance
- Overdue counter links to /queue for quick access

**Harder than expected:** Need to query Projects + QueueTask across all user projects in one call. Using `project_id.in_(pid_list)` for efficient SQL. Balance placeholder — real balance table not yet implemented.

## S03 Project Create/Edit Enhanced + Settings Tab
**Date:** 2026-10-10
**Status:** Built
**Done:**
- Project create/edit modal enhanced: integration selector (4 options), schedule window time pickers (start/end), query modification flags (capital_first/random_caps/typos/trailing_space)
- Backend: Project model gains `scheduling_window`, `query_modifications` JSON columns; Query model gains `query_modifications` JSON column
- Routes updated: create/update project accept new fields, GET returns them
- Settings tab on project detail page for managing integrations/schedule/mods after creation
- Boost modal expanded: time window pickers + day-of-week distribution grid (Mon-Sun toggle buttons)

**Harder than expected:** Editing from listing page needs full project fetch (API call to `/projects/{id}`) since listing only returns summary data. Settings tab saves via `PUT /projects/{id}` with new field groups. Day distribution stored as JSON object in API payload.

## S04 Actions Menu + Copy Project + Clear Queue
**Date:** 2026-10-10
**Status:** Built
**Done:**
- Backend: POST /projects/{id}/copy (copies project+queries+strategy tasks), POST /projects/{id}/auto-stop, POST /projects/{id}/activate, POST /projects/{id}/clear-queue, GET /projects/{id}/clicks
- Frontend: Actions dropdown menu (3-dot button) on project detail header with copy/clear-queue options

## S05 Daily Drill-Down Modal
**Date:** 2026-10-10
**Status:** Built
- Analytics timeline chart bars clickable -> opens drill-down modal with geo/source/position/time breakdown per click

## S06 Queue Page Enhancements + Task Detail Modal
**Date:** 2026-10-10
**Status:** Built
- Source filter buttons (All/Strategy/Autoburst/Proklik) alongside status filters
- Queue table rows clickable -> task detail modal with URL, source, status, position, created time

## S08 Profile Settings — Messenger, External Services, Password
**Date:** 2026-10-10
**Status:** Built (partial)
**Done:**
- Backend: GET/POST `/settings/messenger` — stores telegram_webhook_url and max_connector_id as JSON on user model
- Backend: GET/POST `/settings/external-services` — stores xml_river {user_id, apk} and xml_stock [{name, api_key}] as JSON on user model
- Backend: POST `/password` — validates current password with passlib bcrypt, hashes new password
- Frontend: settings page expanded to 4-column grid: Profile, Messengers, External Services, Password Change
- Frontend: api.ts rewritten with all new methods (messengerSettings, updateMessengerSettings, externalServices, updateExternalServices, changePassword)
- Bulk update endpoint: POST `/{project_id}/queries/bulk-update` accepts body with query_ids array and optional daily_clicks/geo/click_url/text fields

**Harder than expected:** User model doesn't have dedicated messenger_settings or external_services columns — stored as JSON attributes via setattr. Need to query user directly in SQLAlchemy session for commit. Password change requires CryptContext verification round-trip.

## S09 API Documentation Page
**Date:** 2026-10-10
**Status:** Built
**Done:**
- New route `/docs` with Redocly standalone.js from CDN for dynamic OpenAPI rendering
- Fetches spec from `/api/internal/openapi.json`; fallback static docs when spec endpoint unavailable
- Covers all External API endpoints (8 methods), Internal Auth+Users endpoints, data model, JSON schemas for external services

**Harder than expected:** Redocly theme customization via JS object — `theme` option not a string property but a config object with nested layout settings. Fallback docs needed since internal OpenAPI spec endpoint may not exist in dev environments.
