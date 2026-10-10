# GhostLab → TopInjector Architecture Map

## Screen ID mapping (from recon.md)

| ghostlab | topinjector | status |
|----------|-------------|--------|
| S01 Login | /login | ✅ done |
| S02 Projects listing | / | ⚠️ partial — basic table, missing source breakdown, overdue toggle, mass edit, context menu improvements |
| S03 Create/Edit project | / modal + /settings | ⚠️ partial — basic create form, missing integration selector/schedule window/query mods/boost tab |
| S04 Project detail | /projects/[id] | ⚠️ skeleton-only — tabs exist but need full content per recon |
| S05 Analytics | /analytics | ⚠️ stub chart exists, missing charts/detail/edit/export |
| S06 Queue | /queue | ⚠️ basic table exists, missing status/source filters/task detail |
| S07 Status bar | top of layout | ❌ not built |
| S08 Settings | /settings | ⚠️ skeleton-only — profile/messengers/external services needed |
| S09 API docs | /api-docs | ❌ not built |

## Data layers

### Existing (backend)
- `Project` model with geo_settings, integrations JSON fields ✓
- `Query` model with geo, daily_clicks, frequency, boost_min/max ✓
- `QueueTask` model with status/source/position ✓
- `ProjectGroup` with icon ✓
- `ProjectDelegate` with role ✓
- Bulk endpoints: import/export queries ✓, boost ✓
- Queue stats endpoint exists (per-project) ✓
- Queue stats **by source** endpoint exists ✓
- Position trend data endpoint exists ✓
- Markers/Webmarkers models + endpoints ✓

### Backend gaps
- `scheduling_window` (start_time/end_time) on Project — needs migration
- Per-query text modification flags — add to project or query model
- Source breakdown in listing response — need aggregation SQL
- Overdue tasks count endpoint — needs implementation
- Global search across projects+queries — may need full-text index
- Mass operations batch endpoints (delete/start/stop/bulk-edit)

## Implementation order

1. **Listing enhancements** (S02) — source breakdown, overdue toggle
2. **Status bar** (S07) — overdue counter, clicks today, balance
3. **Project create/edit enhanced** (S03) — integration/schedule/geo-mods/boost
4. **Mass edit toolbar** (S02) — selection + bulk actions
5. **Instant click / proklik** (S04) — modal panel
6. **Per-query edit modal** (S04) — geo override, clicks change, boost
7. **Actions menu** (S04) — copy/delegate/auto-stop/clear-queue/delete
8. **Info panel** (S04) — dashboard stats from existing endpoints
9. **Analytics charts + drill-down** (S05)
10. **Queue filters + task detail** (S06)
11. **Settings enhancements** (S08) — messengers/external services
