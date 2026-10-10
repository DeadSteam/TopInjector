# Build Log — GhostLab Replica

## S02 Listing Enhancements
**Date:** 2026-10-10
**Status:** Built
**Done:**
- Source breakdown checkbox toggle — shows/hides columns for completed clicks by source (strategy/autoburst/proklik)
- Overdue toggle — filters projects that have pending tasks past their scheduled time
- Backend endpoints: `/api/projects/{id}/source-breakdown`, `/api/projects/{id}/overdue-count`

**Harder than expected:** Fetching source breakdown per project requires batch API calls. Using Promise.allSettled for resilience. The listing page had to be updated to re-fetch breakdown data after CRUD operations.
