# GhostLab Reconnaissance Map

**Source:** https://ghostlab.ru/docs/interface (and sub-pages)
**Date:** 2026-10-10
**Platform:** Search traffic management panel (behavioral factors for Yandex)

---

## Screens Inventory

| ID | Screen | Section | Key User Actions | Data Layer |
|---|---|---|---|---|
| S01 | Login | Auth | Email/password login, forgot password | User service |
| S02 | Projects Listing | Листинг проектов | Create group/project, filter, search, delegate, bulk edit, context menu | Project + Group + Delegate repos |
| S03 | Create/Edit Project | Создание и настройка | Name, domain, group, integration, strategy, daily limit, schedule window, geo (cities/multigeo), suggestions, query mods, autoburst schedule | Project service + geo codes |
| S04 | Project Detail | Работа внутри проекта | Header with toggle, actions menu, instant click, per-query edit, import/export CSV, info panel, query table, filters, notifications | Project + Query + Queue repos |
| S05 | Analytics | Аналитика | Period filter, project/query/geo/suggestion filters, chart (clicks in top, avg position), editable table, daily drill-down modal | Analytics service |
| S06 | Queue | Очередь задач | Status/source/project/time/text filters, task detail view, clear queue with filters | Queue service |
| S07 | Status Bar | Панель состояния | Overdue tasks count, clicks today (planned/completed), notifications bell, balance display | Queue + User + Balance services |
| S08 | Settings/Profile | Настройки и профиль | Avatar, name/password, messengers (Telegram/Max), API key, external services (XML River, XMLStock) | User service |
| S09 | API Docs | — | Stoplight-powered interactive API docs | N/A |

---

## Core Flows

### Flow 1: Create project → Add queries → Monitor
1. Click "+" on projects listing → fill name/domain/region/strategy
2. Set geo (multigeo with percentages), schedule window, daily limit
3. Import/export CSV queries with click URLs and positions
4. View project detail: info panel, query table, analytics tab
5. Monitor queue for task execution

### Flow 2: Instant click + autoburst
1. Select queries in project → Boost button
2. Set clicks count + interval (e.g., 5 clicks every 2h)
3. Choose start: from now or from tomorrow
4. Or use Проклик for instant clicks on selected/any queries

### Flow 3: Analytics drill-down
1. Open analytics → set filters → view chart + table
2. Click "i" icon on any day cell → see per-click detail (geo, source, position, time, URL)
3. Edit daily clicks directly in analytics table

---

## Components by Screen

### S02 Projects Listing
- Group creation with icons
- Project list table: checkbox, activity toggle, name+group+delegate badge, domain, region, strategy, queries count, plan/day, clicks done, queue, not found, stuck
- Filter panel: group, region, activity, strategy, integration, access (own/delegated-to/delegated-by)
- Search: auto-search + global Ctrl+E (searches groups/projects/queries)
- Configurable columns + pagination
- Overdue tasks toggle (circles icon)
- Source breakdown checkbox (strategy/autoburst/proklik)
- Mass edit toolbar: start/stop, delegate, bulk edit, auto-stop, delete
- Context menu (3 dots): edit, copy (settings only / full), auto-stop, delete

### S03 Create/Edit Project
- Group selector, name, domain
- Integration selector (Integration 2 / Integration 1 for testing / Main Bay Belarus)
- Strategy selector (daily/monthly/hourly)
- Daily limit + schedule window (e.g. 7:00-22:00)
- Geo settings: specific cities, preset city packs (millions, all Russia, Moscow Oblast), multigeo with %, custom codes
- Suggestions input (line by line)
- Query modifications: capital first letter, random caps, typo injection (~20%), trailing space
- Boost tab: time window + day distribution

### S04 Project Detail
- Header: group link, project name, activity toggle, edit button, view settings
- Actions menu: copy, delegate, auto-stop, clear queue, collect frequency (XML River), delete
- Проклик panel: instant clicks (random count / per-query: 1 / daily-cliques-equals / manual / random range)
- Per-query Boost from project: select queries → Boost button → set count+interval → redistribute now/tomorrow
- Mini-modal for query edit: geo override, clicks change (hard/% of frequency), apply click URL, delete
- Import/Export CSV with format download sample
- Info panel: strategy stats, clicks by source, queue statuses, quick links to queue/analytics
- Query table: text, URL, click URL, geo, clicks/day (inline edit), avg position, clicks today, autoburst, frequency
- Query filters: position range, frequency range, text search

### S05 Analytics
- Report export: full report, summary report (user/project/domain/geo/clicks/URL/position)
- Filters: period, projects, query text, geo, suggestion mode (all/with-only/without), avg position threshold
- Inline click count editing per project with confirmation
- Charts: clicks in TOP ranges, avg position by range (toggleable off)
- Analytics table: clickable query, strategy clicks, config URL, actual click URL (toggleable), clicks in period, avg position, daily breakdown (clicks+position per day)
- Daily drill-down modal (i icon): geo per click, source, position, time, click URL, geo+suggestion filters, summary (total/without-without-suggestions/with-suggestions), not-found count

### S06 Queue
- Filters: status (in-queue/in-progress/completed/not-found/stuck), source, project, time range, text search
- Task detail: queue set time, status, source, click URL
- Clear queue with filters

### S07 Status Bar
- Overdue tasks counter + description
- Today clicks: planned vs completed (expect ~50% midday)
- Notifications bell: project updates, proklik send/delete/clear
- Balance display

### S08 Settings/Profile
- Avatar upload
- First/last name
- Password change
- Messengers: Telegram + Max connection
- API key for integrations
- External services: XML River (UserID+APK for frequency), XMLStock (search results keys, multiple)
- Glossary (terms reference table)

---

## Data Sources Needed
- City code database (Yandex geo codes)
- Preset city packs (millions, all Russia, Moscow Oblast, etc.)
- XML River API (UserID + APK for frequency collection)
- XMLStock API (multiple keys for search results)
- Telegram Bot API (notifications)
- Max messenger API
