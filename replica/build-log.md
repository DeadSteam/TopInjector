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
