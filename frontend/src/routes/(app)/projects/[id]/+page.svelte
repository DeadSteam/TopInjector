<script lang="ts">
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	interface QueryRow {
		id: string;
		text: string;
		url: string;
		click_url: string;
		geo: any;
		daily_clicks: number;
		position: number | null;
		completed: number;
		frequency?: number;
	}

	let projectId = $state("");
	let project = $state<any>(null);
	let queries = $state<QueryRow[]>([]);
	let activeTab = $state("queries");
	let loading = $state(true);
	let error = $state("");
	let newQueryText = $state("");
	let groups = $state<any[]>([]);

	// Queue stats & source breakdown
	let queueStats = $state({ pending: 0, in_progress: 0, completed: 0, not_found: 0, stuck: 0 });
	let sourceBreakdown = $state<{ strategy: number; autoburst: number; proklik: number }>({ strategy: 0, autoburst: 0, proklik: 0 });
	let autoRefreshId = $state<number | null>(null);

	// Positions data
	let positionsData = $state<any[]>([]);
	let trendLines = $state<any[]>([]);
	let showChart = $state(true);
	let chartHoverQuery = $state<string | null>(null);

	// Request table stats
	let requestTableData = $state<any[]>([]);

	// Delegates
	let delegates = $state<any[]>([]);
	let newDelegateUserId = $state("");
	let newDelegateRole = $state("view");

	// Markers
	let markersData = $state<any[]>([]);
	let newMarkerName = $state("");
	let newMarkerUrl = $state("");
	let newMarkerSelector = $state("");

	// Per-project analytics
	interface TimelinePoint { date: string; count: number }
	interface TrackingPoint { position: number; date: string | null }
	interface PositionSummary { best_position: number | null; avg_position: number | null; total_records: number }

	let analyticsSummary = $state<any>(null);
	let timelineData = $state<TimelinePoint[]>([]);
	const maxTimelineCount = (timelineData.length > 0 ? Math.max(...timelineData.map((d: any) => d.count), 1) : 1);
	let trackingData = $state<TrackingPoint[]>([]);
	let positionSummary = $state<PositionSummary | null>(null);

	// Webmarkers
	let webmarkersData = $state<any[]>([]);

	// Inline edit state
	let editingQueryId = $state<string | null>(null);
	let editingDailyClicks = $state(0);
	let editingGeo = $state("");
	let editingClickUrl = $state("");

	// Query filters
	let showFilters = $state(false);
	let filterText = $state("");
	let filterPositionMin = $state<number | undefined>(undefined);
	let filterPositionMax = $state<number | undefined>(undefined);
	let filterFrequencyMin = $state<number | undefined>(undefined);

	function clearQueryFilters() {
		filterText = "";
		filterPositionMin = undefined;
		filterPositionMax = undefined;
		filterFrequencyMin = undefined;
	}

	function matchesFilters(query: QueryRow): boolean {
		if (filterText && !query.text.toLowerCase().includes(filterText.toLowerCase())) return false;
		if (filterPositionMin !== undefined && (query.position === null || query.position < filterPositionMin)) return false;
		if (filterPositionMax !== undefined && (query.position === null || query.position > filterPositionMax)) return false;
		if (filterFrequencyMin !== undefined && (query.frequency === undefined || query.frequency === null || query.frequency < filterFrequencyMin)) return false;
		return true;
	}

	function filteredQueries(): QueryRow[] {
		return queries.filter(matchesFilters);
	}

	// Project settings state
	let settingIntegration = $state("default");
	let settingScheduleStart = $state("");
	let settingScheduleEnd = $state("");
	let settingModsCapital = $state(false);
	let settingModsRandomCaps = $state(false);
	let settingModsTypos = $state(false);
	let settingModsTrailingSpace = $state(false);
	let settingsSaving = $state(false);
	let settingsSaved = $state(false);

	// Bulk edit modal
	let showBulkEdit = $state(false);
	let bulkEditGeoJson = $state("");
	let bulkEditDailyClicks = $state(0);
	let bulkEditApplyClickUrl = $state("");
	let bulkEditApplyClickUrlToggle = $state(false);
	let bulkDeleteSelected = $state(false);
	let bulkLoading = $state(false);

	// Task detail modal (queue drill-down)
	let showTaskDetail = $state(false);
	let taskDetail: any = null;

	// Daily drill-down modal
	let showDrillDown = $state(false);
	let drillDate = $state("");
	let drillClicks: any[] = [];
	let drillLoading = $state(false);

	// Copy project modal state
	let copyProjectName = $state("");

	// Proklik modal
	let showProklik = $state(false);
	let proklikCount = $state(1);
	let proklikQueries: string[] = [];
	let proklikMode = $state<"all" | "selected">("all");
	let proklikLoading = $state(false);

	// Selection
	let selectedQueryIds = new Set<string>();

	// Boost modal
	let showBoost = $state(false);
	let boostDailyClicks = $state(10);
	let boostInterval = $state(3600);
	let boostStartFromNow = $state(true);
	let boostScheduleStart = $state("");
	let boostScheduleEnd = $state("");
	let boostDayDist: Record<string, boolean> = { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false };
	let boostLoading = $state(false);

	const statusColors: Record<string, string> = {
		pending: 'bg-yellow-100 text-yellow-800',
		in_progress: 'bg-blue-100 text-blue-800',
		completed: 'bg-green-100 text-green-800',
		not_found: 'bg-red-100 text-red-800',
		stuck: 'bg-orange-100 text-orange-800',
	};

	const statusLabels: Record<string, string> = {
		pending: 'Ожидает',
		in_progress: 'Выполняется',
		completed: 'Завершён',
		not_found: 'Не найден',
		stuck: 'Завис',
	};

	async function loadProject() {
		try {
			project = await api.projects.get(projectId);
			await loadQueries();
			await loadQueueStats();
			await loadSourceBreakdown();
			await loadGroups();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	async function loadQueries() {
		try {
			queries = await api.projects.queries(projectId);
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки запросов";
		}
	}

	async function loadQueueStats() {
		try { queueStats = await api.projects.queueStats(projectId); } catch {}
	}

	async function loadSourceBreakdown() {
		try { sourceBreakdown = await api.projects.queueStatsBySource(projectId); } catch {}
	}

	async function loadGroups() {
		try { groups = await api.groups.list(); } catch {}
	}

	async function loadPositions() {
		try {
			const data = await api.projects.positions(projectId);
			positionsData = data.history || [];
		} catch { positionsData = []; }
		await loadTrend();
	}

	async function loadTrend() {
		try {
			const data = await api.projects.trend(projectId);
			trendLines = data.lines || [];
		} catch { trendLines = []; }
	}

	async function loadRequestTable() {
		try {
			const data = await api.projects.requestTable(projectId);
			requestTableData = data.queries || [];
		} catch { requestTableData = []; }
	}

	async function loadDelegates() {
		try { delegates = await api.projects.delegates(projectId); } catch { delegates = []; }
	}

	async function addDelegate() {
		if (!newDelegateUserId.trim()) return;
		try {
			await api.projects.addDelegate(projectId, { delegate_user_id: newDelegateUserId.trim(), role: newDelegateRole });
			newDelegateUserId = "";
			newDelegateRole = "view";
			await loadDelegates();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка добавления делегата"; }
	}

	async function removeDelegate(userId: string) {
		if (!confirm("Убрать доступ?")) return;
		try { await api.projects.removeDelegate(projectId, userId); await loadDelegates(); }
		catch (err) { error = err instanceof Error ? err.message : "Ошибка удаления"; }
	}

	async function loadProjectAnalytics() {
		try { analyticsSummary = await api.analytics.summary(projectId); } catch { analyticsSummary = null; }
		try {
			const tl = await api.analytics.clicks(projectId);
			timelineData = tl.timeline || [];
		} catch { timelineData = []; }
		try {
			const tr = await api.analytics.trackingPositions(projectId);
			trackingData = tr.tracking || [];
			positionSummary = tr.summary || null;
		} catch { trackingData = []; positionSummary = null; }
	}

	async function loadMarkers() {
		try { markersData = await api.projects.markers(projectId); } catch { markersData = []; }
	}

	async function addMarker() {
		if (!newMarkerName.trim() || !newMarkerUrl.trim()) return;
		try {
			await api.projects.createMarker(projectId, { name: newMarkerName, url: newMarkerUrl, css_selector: newMarkerSelector });
			newMarkerName = ""; newMarkerUrl = ""; newMarkerSelector = "";
			await loadMarkers();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка создания маркера"; }
	}

	async function deleteMarker(markerId: string) {
		if (!confirm("Удалить маркер?")) return;
		try { await api.projects.deleteMarker(projectId, markerId); await loadMarkers(); }
		catch (err) { error = err instanceof Error ? err.message : "Ошибка удаления"; }
	}

	async function loadWebmarkers() {
		try { webmarkersData = await api.projects.webmarkers(projectId); } catch { webmarkersData = []; }
	}

	async function addWebmarker(platform: string) {
		try { await api.projects.createWebmarker(projectId, { platform }); await loadWebmarkers(); }
		catch (err) { error = err instanceof Error ? err.message : "Ошибка создания"; }
	}

	async function verifyWebmarker(wmId: string) {
		try { await api.projects.verifyWebmarker(projectId, wmId); await loadWebmarkers(); }
		catch (err) { error = err instanceof Error ? err.message : "Ошибка верификации"; }
	}

	async function deleteWebmarker(wmId: string) {
		if (!confirm("Удалить вебмаркер?")) return;
		try { await api.projects.deleteWebmarker(projectId, wmId); await loadWebmarkers(); }
		catch (err) { error = err instanceof Error ? err.message : "Ошибка удаления"; }
	}

	async function addQuery() {
		if (!newQueryText.trim()) return;
		try {
			await api.projects.addQuery(projectId, { text: newQueryText });
			newQueryText = "";
			await loadQueries();
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка добавления"; }
	}

	async function toggleActivity() {
		if (!project) return;
		try {
			const newActive = !project.is_active;
			await api.projects.activate(projectId, newActive);
			project.is_active = newActive;
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка переключения активности"; }
	}

	async function deleteProject() {
		if (!confirm("Удалить проект? Все запросы и задачи будут удалены.")) return;
		try {
			await api.projects.delete(projectId);
			window.location.href = "/";
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка удаления"; }
	}

	// Actions menu state
	let showActionsMenu = $state(false);

	async function copyProject() {
		const name = prompt("Имя скопированного проекта:");
		if (!name) return;
		try {
			const data = await api.projects.copyProject(projectId, { name });
			alert(`Проект скопирован: ${data.id}`);
			window.location.href = `/projects/${data.id}`;
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка копирования"; }
	}

	async function clearQueueAction() {
		if (!confirm("Очистить все pending и in_progress задачи?")) return;
		try {
			const data = await api.projects.clearQueue(projectId, { statuses: ["pending", "in_progress"] });
			await loadQueueStats();
			alert(`Очищено. Осталось: ${data.remaining}`);
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка очистки очереди"; }
	}

	async function openDailyDrillDown(dateStr: string) {
		drillDate = dateStr;
		showDrillDown = true;
		drillLoading = true;
		drillClicks = [];
		try {
			drillClicks = await api.projects.getClicks(projectId, { date_str: dateStr });
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки кликов";
		} finally {
			drillLoading = false;
		}
	}

	async function openTaskDetail(taskId: string) {
		showTaskDetail = true;
		taskDetail = null; // will be filled when clicked
	}

	// Inline edit
	function startEdit(query: QueryRow) {
		editingQueryId = query.id;
		editingDailyClicks = query.daily_clicks;
		editingGeo = query.geo ? JSON.stringify(query.geo, null, 2) : "";
		editingClickUrl = query.click_url || "";
	}

	async function saveEdit(queryId: string) {
		if (!editingQueryId) return;
		try {
			const updateData: any = { daily_clicks: Math.max(0, editingDailyClicks) };
			if (editingGeo) {
				try { updateData.geo = JSON.parse(editingGeo); } catch { /* keep original */ }
			}
			if (editingClickUrl) updateData.click_url = editingClickUrl;
			await api.projects.updateQuery(projectId, queryId, updateData);
			await loadQueries();
			await loadQueueStats();
			editingQueryId = null;
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка сохранения"; }
	}

	function cancelEdit() { editingQueryId = null; }

	async function quickIncrDaily(queryId: string, current: number) {
		try {
			await api.projects.updateQuery(projectId, queryId, { daily_clicks: current + 1 });
			await loadQueries();
		} catch { /* silent */ }
	}

	async function quickDecrDaily(queryId: string, current: number) {
		if (current <= 0) return;
		try {
			await api.projects.updateQuery(projectId, queryId, { daily_clicks: current - 1 });
			await loadQueries();
		} catch { /* silent */ }
	}

	// Proklik
	async function sendProklik() {
		if (proklikLoading) return;
		proklikLoading = true;
		try {
			const data: any = { project_id: projectId, count: proklikCount };
			if (proklikMode === "selected" && proklikQueries.length > 0) {
				data.query_ids = proklikQueries;
			}
			await api.queue.proklik(data);
			showProklik = false;
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка отправки проклика"; }
		proklikLoading = false;
	}

	function toggleSelect(queryId: string) {
		if (selectedQueryIds.has(queryId)) selectedQueryIds.delete(queryId);
		else selectedQueryIds.add(queryId);
	}

	function selectAll() {
		const targets = showFilters ? filteredQueries() : queries;
		if (targets.every(q => selectedQueryIds.has(q.id))) {
			selectedQueryIds.clear();
		} else {
			targets.forEach(q => selectedQueryIds.add(q.id));
		}
	}

	async function sendBoost() {
		if (selectedQueryIds.size === 0 || boostLoading) return;
		const activeDays = Object.keys(boostDayDist).filter(k => boostDayDist[k]);
		boostLoading = true;
		try {
			await api.projects.boost(projectId, {
				query_ids: [...selectedQueryIds],
				daily_clicks: Math.max(1, boostDailyClicks),
				interval_seconds: boostInterval,
				start_from_now: boostStartFromNow,
				schedule_window: (boostScheduleStart && boostScheduleEnd) ? { start: boostScheduleStart, end: boostScheduleEnd } : null,
				day_distribution: activeDays.length > 0 ? Object.fromEntries(activeDays.map(d => [d, true])) : undefined,
			});
			showBoost = false;
			await loadQueries();
			await loadQueueStats();
			selectedQueryIds.clear();
			boostDayDist = { mon: false, tue: false, wed: false, thu: false, fri: false, sat: false, sun: false };
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка буста"; }
		boostLoading = false;
	}

	async function deleteQuery(queryId: string) {
		if (!confirm("Удалить запрос?")) return;
		try {
			await api.projects.deleteQuery(projectId, queryId);
			await loadQueries();
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка удаления запроса"; }
	}

	// Bulk update queries
	async function bulkUpdate() {
		if (selectedQueryIds.size === 0 || bulkLoading) return;
		bulkLoading = true;
		try {
			const updates: Record<string, any> = { query_ids: [...selectedQueryIds] };
			if (bulkEditDailyClicks > 0) updates.daily_clicks = bulkEditDailyClicks;
			if (bulkEditGeoJson.trim()) {
				try { updates.geo = JSON.parse(bulkEditGeoJson); } catch { error = "Неверный JSON для гео"; }
			}
			if (bulkEditApplyClickUrlToggle && bulkEditApplyClickUrl.trim()) updates.click_url = bulkEditApplyClickUrl;
			await api.projects.bulkUpdateQueries(projectId, updates);
			selectedQueryIds.clear();
			showBulkEdit = false;
			bulkEditGeoJson = ""; bulkEditDailyClicks = 0; bulkEditApplyClickUrl = ""; bulkEditApplyClickUrlToggle = false;
			await loadQueries();
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка массового обновления"; }
		bulkLoading = false;
	}

	// Bulk delete selected queries
	async function bulkDeleteQueries() {
		if (selectedQueryIds.size === 0) return;
		if (!confirm(`Удалить ${selectedQueryIds.size} запрос(ов)?`)) return;
		try {
			for (const qid of selectedQueryIds) {
				await api.projects.deleteQuery(projectId, qid);
			}
			selectedQueryIds.clear();
			await loadQueries();
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка массового удаления"; }
	}

	function openBulkEdit() {
		if (selectedQueryIds.size === 0) return;
		showBulkEdit = true;
		bulkEditDailyClicks = 0; bulkEditGeoJson = ""; bulkEditApplyClickUrl = ""; bulkEditApplyClickUrlToggle = false;
	}

	function toggleChartView() { showChart = !showChart; }

	function getChartDims() {
		const containerW = 700;
		const containerH = 320;
		const marginL = 50;
		const marginR = 20;
		const marginT = 20;
		const marginB = 60;
		const innerW = containerW - marginL - marginR;
		const innerH = containerH - marginT - marginB;
		return { containerW, containerH, marginL, marginR, marginT, marginB, innerW, innerH };
	}

	function buildChartPath(lines: any[]) {
		if (!lines.length) return "";
		const dates = lines[0].data.map((d: any) => d.date);
		if (!dates.length) return "";

		const allPositions = lines.flatMap(l => l.data.map(d => d.position));
		const minP = Math.max(1, Math.min(...allPositions) - 1);
		const maxP = Math.min(20, Math.max(...allPositions) + 1);

		const { innerW, innerH } = getChartDims();
		const xScale = (i: number) => (dates.length > 1 ? (i / (dates.length - 1)) * innerW : innerW / 2);
		const yScale = (p: number) => innerH - ((p - minP) / (maxP - minP || 1)) * innerH;

		let pathStr = "";
		for (const line of lines) {
			const pts = line.data.filter((d: any) => d.position >= 1);
			if (pts.length < 2) continue;
		 const segments = pts.map((d: any, i: number) => {
				const absI = line.data.indexOf(d);
				const x = xScale(absI);
				const y = yScale(d.position);
				return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
			}).join(' ');
			pathStr += segments + " ";
		}
		return pathStr.trim();
	}

	function buildChartPoints(lines: any[]) {
		if (!lines.length) return [];
		const dates = lines[0].data.map((d: any) => d.date);
		if (!dates.length) return [];

		const allPositions = lines.flatMap(l => l.data.map(d => d.position));
		const minP = Math.max(1, Math.min(...allPositions) - 1);
		const maxP = Math.min(20, Math.max(...allPositions) + 1);

		const { innerW, innerH } = getChartDims();
		const xScale = (i: number) => (dates.length > 1 ? (i / (dates.length - 1)) * innerW : innerW / 2);
		const yScale = (p: number) => innerH - ((p - minP) / (maxP - minP || 1)) * innerH;

		const points: any[] = [];
		for (const line of lines) {
			line.data.forEach((d: any, idx: number) => {
				if (d.position < 1) return;
				points.push({ x: xScale(idx), y: yScale(d.position), query: line.text, date: d.date, position: d.position });
			});
		}
		return points;
	}

	function chartMouseMove(e: MouseEvent) {
		const svg = e.currentTarget as SVGElement;
		if (!svg || !chartHoverQuery) return;
		const rect = svg.getBoundingClientRect();
		const mouseX = e.clientX - rect.left;
		const mouseY = e.clientY - rect.top;
		const { marginL, innerW } = getChartDims();

		// Find nearest date to cursor
		if (trendLines.length === 0) return;
		const dates = trendLines[0].data.map((d: any) => d.date);
		if (!dates.length) return;

		const xScale = (i: number) => (dates.length > 1 ? (i / (dates.length - 1)) * innerW : innerW / 2);
		const totalX = mouseX + marginL;
		let nearestIdx = Math.round((totalX / innerW) * (dates.length - 1));
		nearestIdx = Math.max(0, Math.min(dates.length - 1, nearestIdx));

		hoverDate = dates[nearestIdx];
	}

	let hoverDate = $state<string | null>(null);

	function startAutoRefresh() {
		stopAutoRefresh();
		autoRefreshId = window.setInterval(async () => {
			if (activeTab === 'queue') await loadQueueStats();
			if (activeTab === 'positions') await loadPositions();
		}, 10000);
	}

	function stopAutoRefresh() {
		if (autoRefreshId) { clearInterval(autoRefreshId); autoRefreshId = null; }
	}

	onMount(() => {
		projectId = window.location.pathname.split('/projects/')[1] || "";
		loadProject();
	});

	function switchTab(tab: string) {
		activeTab = tab;
		if (tab === 'positions') loadPositions();
		if (tab === 'markers') loadMarkers();
		if (tab === 'webmaster') loadWebmarkers();
		if (tab === 'stats') loadRequestTable();
		if (tab === 'delegates') loadDelegates();
		if (tab === 'analytics') loadProjectAnalytics();
		if (tab === 'settings' && project) {
			settingIntegration = project.integrations?.integration_type || "default";
			settingScheduleStart = project.scheduling_window?.start || "";
			settingScheduleEnd = project.scheduling_window?.end || "";
			const qm = project.query_modifications || {};
			settingModsCapital = !!qm.capital_first;
			settingModsRandomCaps = !!qm.random_caps;
			settingModsTypos = !!qm.typos;
			settingModsTrailingSpace = !!qm.trailing_space;
			settingsSaved = false;
		}
		startAutoRefresh();
	}

	async function saveProjectSettings() {
		if (!projectId) return;
		settingsSaving = true;
		try {
			const data: any = {
				integrations: {},
				scheduling_window: null,
				query_modifications: {},
			};
			if (settingIntegration !== "default") data.integrations.integration_type = settingIntegration;
			if (settingScheduleStart && settingScheduleEnd) data.scheduling_window = { start: settingScheduleStart, end: settingScheduleEnd };
			const mods: Record<string, boolean> = {};
			if (settingModsCapital) mods.capital_first = true;
			if (settingModsRandomCaps) mods.random_caps = true;
			if (settingModsTypos) mods.typos = true;
			if (settingModsTrailingSpace) mods.trailing_space = true;
			data.query_modifications = mods;
			await api.projects.update(projectId, data);
			settingsSaved = true;
			setTimeout(() => { settingsSaved = false; }, 3000);
			// Reload project to reflect changes
			await loadProject();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка сохранения настроек"; }
		settingsSaving = false;
	}

	onDestroy(() => { stopAutoRefresh(); });

	const tabList = [
		{ key: "queries", label: "Запросы" },
		{ key: "queue", label: "Очередь" },
		{ key: "analytics", label: "Аналитика" },
		{ key: "stats", label: "Статистика" },
		{ key: "positions", label: "Позиции" },
		{ key: "delegates", label: "Делегаты" },
		{ key: "markers", label: "Маркеры" },
		{ key: "webmaster", label: "ВебМастер" },
		{ key: "settings", label: "Настройки" },
	];

	const strategyLabels: Record<string, string> = { daily: "Ежедневная", monthly: "Ежемесячная", hourly: "Почасовая" };

	// Day distribution labels
	const dayLabels = [
		{ key: "mon", label: "Пн" },
		{ key: "tue", label: "Вт" },
		{ key: "wed", label: "Ср" },
		{ key: "thu", label: "Чт" },
		{ key: "fri", label: "Пт" },
		{ key: "sat", label: "Сб" },
		{ key: "sun", label: "Вс" },
	];

	function groupLink(groupId: string | null) {
		if (!groupId) return null;
		return `/projects?group_id=${groupId}`;
	}
</script>

<div class="p-6">
	<!-- Project header with group & activity -->
	<div class="mb-6">
		<a href="/" class="text-sm text-blue-600 hover:text-blue-700 mb-2 inline-block">← Все проекты</a>

		{#if project}
			<div class="flex items-start justify-between gap-4">
				<div class="flex-1">
					<div class="flex items-center gap-3">
						<h1 class="text-xl font-bold text-gray-900">{project.name}</h1>
						{#if project.group_name}
							<span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-blue-50 text-blue-700 border border-blue-200">
								<a href={groupLink(project.group_id)} class="hover:underline">{project.group_name}</a>
							</span>
						{/if}
						<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium {project.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-600'}">
							{project.is_active ? 'Активен' : 'На паузе'}
						</span>
					</div>

					<p class="text-sm text-gray-500 mt-1">{project.domain} · {project.region || '—'} · {strategyLabels[project.strategy_type] || project.strategy_type} стратегия</p>

					<!-- Info panel: limits & clicks by source -->
					<div class="mt-3 grid grid-cols-4 gap-4">
						<div class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
							<p class="text-xs text-gray-500">Лимит/день</p>
							<p class="text-lg font-semibold text-gray-900">{project.daily_limit}</p>
						</div>
						<div class="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
							<p class="text-xs text-gray-500">Запросов</p>
							<p class="text-lg font-semibold text-blue-600">{queries.length}</p>
						</div>
						<div class="bg-white border border-green-200 rounded-lg px-3 py-2">
							<p class="text-xs text-gray-500">Кликов (стратегия)</p>
							<p class="text-lg font-semibold text-green-600">{sourceBreakdown.strategy || 0}</p>
						</div>
						<div class="bg-white border border-purple-200 rounded-lg px-3 py-2">
							<p class="text-xs text-gray-500">Прокликов</p>
							<p class="text-lg font-semibold text-purple-600">{sourceBreakdown.proklik || 0}</p>
						</div>
					</div>
				</div>

				<!-- Activity toggle & actions -->
				<div class="flex flex-col gap-2 relative">
					<button onclick={toggleActivity} class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors {project.is_active ? 'bg-gray-100 hover:bg-gray-200 text-gray-700' : 'bg-green-600 hover:bg-green-700 text-white'}">
						<!-- Switch icon -->
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							{#if project.is_active}
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.657L5.636 18.364M18.364 18.364L5.636 5.657"/>
							{:else}
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
							{/if}
						</svg>
						{project.is_active ? 'Остановить' : 'Запустить'}
					</button>
					<div class="flex gap-2">
						<button onclick={deleteProject} class="px-4 py-2 rounded-lg text-sm font-medium bg-red-50 hover:bg-red-100 text-red-600 transition-colors">Удалить</button>
						<div class="relative">
							<button onclick={() => showActionsMenu = !showActionsMenu} class="px-2 py-2 rounded-lg text-sm bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors">
								<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20"><circle cx="5" cy="10" r="1.5"/><circle cx="10" cy="10" r="1.5"/><circle cx="15" cy="10" r="1.5"/></svg>
							</button>
							{#if showActionsMenu}
								<div class="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 z-50 py-1">
									<button onclick={() => { copyProject(); showActionsMenu = false; }} class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 text-gray-700">Копировать проект</button>
									<button onclick={() => { clearQueueAction(); showActionsMenu = false; }} class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 text-gray-700">Очистить очередь</button>
									<button onclick={() => { showActionsMenu = false; }} class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50 text-gray-700">Перейти</button>
								</div>
							{/if}
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>

	<!-- Tabs -->
	<div class="border-b border-gray-200 mb-6">
		<nav class="-mb-px flex space-x-6">
			{#each tabList as tab}
				<button
					class={`py-3 px-1 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
					onclick={() => switchTab(tab.key)}
				>
					{tab.label}
				</button>
			{/each}
		</nav>
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}
		<!-- Queries tab -->
		{#if activeTab === 'queries'}
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<!-- Table toolbar -->
				<div class="px-4 py-3 border-b border-gray-200 flex items-center justify-between flex-wrap gap-2">
					<form onsubmit={(e) => { e.preventDefault(); addQuery(); }} class="flex items-center gap-2">
						<input type="text" bind:value={newQueryText} placeholder="Добавить запрос..." class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none w-64" />
						<button type="submit" class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">Добавить</button>
					</form>
					<div class="flex items-center gap-2">
							<label class="px-2 py-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white rounded cursor-pointer font-medium transition-colors">
								Импорт CSV
								<input type="file" accept=".csv" class="hidden" onchange={handleImportFile} />
							</label>
							<button onclick={handleExport} class="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors font-medium">Экспорт CSV</button>
						{#if selectedQueryIds.size > 0}
							<button onclick={openBulkEdit} class="px-3 py-1.5 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors font-medium">Ред-кт ({selectedQueryIds.size})</button>
							<button onclick={bulkDeleteQueries} class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-medium">Удалить ({selectedQueryIds.size})</button>
							<button onclick={() => selectedQueryIds.clear()} class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Снять все</button>
						{:else}
							<button onclick={selectAll} class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Выбрать все</button>
						{/if}
						<button onclick={() => { proklikMode = "all"; showProklik = true; }} class="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors font-medium">Проклик</button>
							<button onclick={() => showFilters = !showFilters} class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">&#9889; Фильтры</button>
					</div>
				</div>

					{#if showFilters}
						<div class="px-4 py-3 border-b border-gray-200 bg-gray-50 flex flex-wrap items-end gap-3">
							<div>
								<label class="block text-xs text-gray-500 mb-1">Текст запроса</label>
								<input type="text" bind:value={filterText} placeholder="Поиск по тексту..." class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none w-48" />
							</div>
							<div>
								<label class="block text-xs text-gray-500 mb-1">Позиция от</label>
								<input type="number" bind:value={filterPositionMin} placeholder="1" min="1" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none w-24" />
							</div>
							<div>
								<label class="block text-xs text-gray-500 mb-1">Позиция до</label>
								<input type="number" bind:value={filterPositionMax} placeholder="беск." min="1" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none w-24" />
							</div>
							<div>
								<label class="block text-xs text-gray-500 mb-1">Частота от</label>
								<input type="number" bind:value={filterFrequencyMin} placeholder="0" min="0" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none w-24" />
							</div>
							<button onclick={clearQueryFilters} class="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors">&#8634; Сбросить</button>
							</div>
						{#if queries.length}
							<div class="px-4 py-2 text-xs text-gray-500 bg-white border-b border-gray-200">
								Показано {filteredQueries().length} из {queries.length} запросов
								{#if filterText || filterPositionMin !== undefined || filterPositionMax !== undefined || filterFrequencyMin !== undefined}
									<span class="ml-1 text-blue-600">(применены фильтры)</span>
								{/if}
							</div>
						{/if}
					{/if}

				<!-- Queries table -->
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-3 py-3 w-10"></th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Запрос</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">URL</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Гео</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Кликов/день</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">click_url</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Сделано</th>
								<th class="px-4 py-3 text-right font-medium text-gray-600">Действия</th>
							</tr>
						</thead>
						<tbody>
							{#each filteredQueries() as query}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors {selectedQueryIds.has(query.id) ? 'bg-purple-50' : ''}">
									<td class="px-3 py-3">
										<input type="checkbox" bind:group={proklikQueries} value={query.id} checked={selectedQueryIds.has(query.id)} onchange={() => toggleSelect(query.id)} class="rounded border-gray-300 text-purple-600 focus:ring-purple-500" />
									</td>
									{#if editingQueryId === query.id}
										<!-- Inline edit -->
										<td colspan="8">
											<div class="px-4 py-3 space-y-2 bg-white">
												<div class="grid grid-cols-2 gap-3">
													<div>
														<label class="text-xs text-gray-500">Гео (JSON)</label>
														<textarea bind:value={editingGeo} rows="2" class="w-full border border-gray-300 rounded px-2 py-1 text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
													</div>
													<div>
														<label class="text-xs text-gray-500">Кликов/день</label>
														<input type="number" bind:value={editingDailyClicks} min="0" class="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
													</div>
												</div>
												<div>
													<label class="text-xs text-gray-500">click_url</label>
													<input type="url" bind:value={editingClickUrl} class="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
												</div>
												<div class="flex gap-2 justify-end">
													<button onclick={cancelEdit} class="px-3 py-1 text-xs border rounded hover:bg-gray-50 transition-colors">Отмена</button>
													<button onclick={() => saveEdit(query.id)} class="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors">Сохранить</button>
												</div>
											</div>
										</td>
									{:else}
										<td class="px-4 py-3 font-medium text-gray-900">{query.text}</td>
										<td class="px-4 py-3 text-blue-600 truncate max-w-[150px]"><a href={query.url} target="_blank" class="hover:underline">{query.url ? (query.url.length > 20 ? query.url.slice(0, 20) + '…' : query.url) : '—'}</a></td>
										<td class="px-4 py-3 text-gray-600 text-xs max-w-[150px] truncate" title={query.geo ? JSON.stringify(query.geo) : ''}>{query.geo && Object.keys(query.geo).length > 0 ? (typeof query.geo === 'string' ? query.geo : JSON.stringify(query.geo)) : '—'}</td>
										<td class="px-4 py-3">
											<div class="flex items-center gap-1 justify-end"><button onclick={(e) => { e.stopPropagation(); quickDecrDaily(query.id, query.daily_clicks); }} class="w-6 h-6 flex items-center justify-center text-xs rounded bg-gray-100 hover:bg-red-50 hover:text-red-600 transition-colors font-bold">−</button><span class="text-sm font-medium tabular-nums w-12 text-center cursor-pointer hover:text-blue-600" title="Нажмите для редактирования">{query.daily_clicks}</span><button onclick={(e) => { e.stopPropagation(); quickIncrDaily(query.id, query.daily_clicks); }} class="w-6 h-6 flex items-center justify-center text-xs rounded bg-gray-100 hover:bg-green-50 hover:text-green-600 transition-colors font-bold">+</button></div>
										</td>
										<td class="px-4 py-3 text-blue-600 truncate max-w-[150px] text-xs"><a href={query.click_url} target="_blank" class="hover:underline">{query.click_url ? (query.click_url.length > 20 ? query.click_url.slice(0, 20) + '…' : query.click_url) : '—'}</a></td>
										<td class="px-4 py-3">
											<span class="font-medium text-green-600">{query.completed.toLocaleString()}</span>
										</td>
										<td class="px-4 py-3 text-right">
											<button onclick={() => deleteQuery(query.id)} class="text-red-500 hover:text-red-700 text-xs" title="Удалить запрос">×</button>
										</td>
									{/if}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				{#if queries.length === 0}
					<div class="px-4 py-12 text-center text-gray-400">Нет запросов. Добавьте первый запрос для начала работы.</div>
				{/if}
			</div>
		{:else if activeTab === 'queue'}
			<!-- Queue tab -->
			<div class="mb-6">
				<p class="text-sm text-gray-500 mb-4">Обновление каждые 10 секунд. <a href="/queue" class="text-blue-600 hover:text-blue-700">Перейти к полному списку задач →</a></p>

				<div class="grid grid-cols-2 gap-4 mb-4">
					<div class="bg-purple-50 border border-purple-200 rounded-lg p-3 text-center">
						<p class="text-xs text-gray-500">Прокликов завершено</p>
						<p class="text-xl font-bold text-purple-700">{sourceBreakdown.proklik || 0}</p>
					</div>
					<div class="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
						<p class="text-xs text-gray-500">Стратегия завершено</p>
						<p class="text-xl font-bold text-blue-700">{sourceBreakdown.strategy || 0}</p>
					</div>
				</div>

				<div class="grid grid-cols-5 gap-4">
					{#each ['pending', 'in_progress', 'completed', 'not_found', 'stuck'] as status}
						<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm text-center">
							<span class="inline-flex px-2 py-1 rounded-full text-xs font-medium {statusColors[status]}">{statusLabels[status]}</span>
							<p class="text-2xl font-bold text-gray-900 mt-2">{queueStats[status as keyof typeof queueStats] || 0}</p>
						</div>
					{/each}
				</div>
			</div>

		{:else if activeTab === 'analytics'}
			<!-- Per-project analytics -->
			{#if analyticsSummary}
				<div class="grid grid-cols-2 gap-4 mb-6">
					<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
						<p class="text-sm text-gray-500">Всего кликов</p>
						<p class="text-3xl font-bold text-gray-900 mt-1">{analyticsSummary.total_clicks?.toLocaleString() ?? '—'}</p>
					</div>
					<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
						<p class="text-sm text-gray-500">Успешность</p>
						<p class="text-3xl font-bold text-green-600 mt-1">
							{analyticsSummary.completed_rate ? (analyticsSummary.completed_rate * 100).toFixed(1) + '%' : '—'}
						</p>
					</div>
				</div>
			{/if}

			<!-- Timeline bar chart -->
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
				<h3 class="font-medium text-gray-900 mb-4">Клики по дням</h3>

				{#if timelineData.length === 0}
					<div class="h-48 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
						Нет данных о кликах. Клики начнут отображаться после выполнения первых задач.
					</div>
				{:else}
					<div class="flex items-end gap-0.5 h-48 px-1">
						{#each timelineData as point, i}
							<div class="flex-1 flex flex-col items-center group relative cursor-pointer" onclick={() => openDailyDrillDown(point.date)}>
								<div class="absolute bottom-full mb-2 hidden group-hover:block bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10 pointer-events-none">
									{new Date(point.date).toLocaleDateString("ru-RU")}: {point.count} кликов
								</div>
								<div class="w-full bg-blue-500 hover:bg-blue-600 rounded-t transition-colors" style="height: calc({point.count} / {maxTimelineCount} * 100%)"></div>
							</div>
						{/each}
					</div>
			</div>
			</div>
		</div>
		<!-- Position tracking -->
		{#if positionSummary && positionSummary.total_records > 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
				<h3 class="font-medium text-gray-900 mb-4">Позиции</h3>
				<div class="flex gap-4 mb-4">
					<div class="px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
						<span class="text-xs text-green-700">Лучшая:</span>
						<span class="text-sm font-bold text-green-900 ml-1">#{positionSummary.best_position}</span>
					</div>
					<div class="px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg">
						<span class="text-xs text-blue-700">Средняя:</span>
						<span class="text-sm font-bold text-blue-900 ml-1">{positionSummary.avg_position}</span>
					</div>
				</div>
			</div>

			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Позиция</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Дата</th>
							</tr>
						</thead>
						<tbody>
							{#each trackingData.slice(-50).reverse() as point}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-mono font-bold {point.position <= 3 ? 'text-green-600' : point.position <= 10 ? 'text-blue-600' : 'text-gray-500'}">
										#{point.position}
									</td>
									<td class="px-4 py-3 text-gray-500">{point.date ? new Date(point.date).toLocaleDateString('ru-RU') : '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{:else if analyticsSummary === null && timelineData.length === 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">
				Нет данных аналитики. Данные появятся после выполнения первых задач очереди.
			</div>

	{:else if activeTab === 'stats'}
		<!-- Stats tab: per-query statistics -->
		<div class="mb-4">
			<p class="text-sm text-gray-500">Статистика по каждому запросу: частота, средняя позиция, завершённые задачи.</p>
		</div>

		{#if requestTableData.length === 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">Нет статистики. Данные появятся после завершения первых задач очереди.</div>
		{:else}
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Запрос</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Частота</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Кликов/день</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Ср. позиция</th>
								<th class="px-4 py-3 text-right font-medium text-gray-600">Всего задач</th>
								<th class="px-4 py-3 text-right font-medium text-gray-600">Завершено</th>
							</tr>
						</thead>
						<tbody>
							{#each requestTableData as row}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-medium text-gray-900 max-w-[300px] truncate" title={row.text}>{row.text}</td>
									<td class="px-4 py-3 text-gray-700">{row.frequency ?? '—'}</td>
									<td class="px-4 py-3 text-gray-700">{row.daily_clicks ?? '—'}</td>
									<td class="px-4 py-3">
										{#if row.avg_position != null}
											<span class={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
												row.avg_position <= 3 ? 'bg-green-100 text-green-800' :
												row.avg_position <= 10 ? 'bg-blue-100 text-blue-800' :
												'bg-yellow-100 text-yellow-800'
											}`}>#{row.avg_position}</span>
										{:else}
											<span class="text-gray-400">—</span>
										{/if}
									</td>
									<td class="px-4 py-3 text-right text-gray-700">{row.total_tasks.toLocaleString()}</td>
									<td class="px-4 py-3 text-right">
										<span class="font-medium {row.completed_count > 0 ? 'text-green-600' : 'text-gray-400'}">
											{row.completed_count.toLocaleString()}
										</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

	{:else if activeTab === 'positions'}
		<!-- Positions tab -->
		<div class="mb-4 flex items-center justify-between">
			<div>
				<p class="text-sm text-gray-500">История позиций по запросам. Обновление каждые 10 секунд.</p>
			</div>
			{#if trendLines.length > 0 && positionsData.length > 0}
				<div class="flex gap-2">
					<button onclick={() => { showChart = true; }} class={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${showChart ? 'bg-blue-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}`}>График</button>
					<button onclick={() => { showChart = false; }} class={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${!showChart ? 'bg-blue-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}`}>Таблица</button>
				</div>
			{/if}
		</div>

		{#if trendLines.length === 0 && positionsData.length === 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">Нет данных о позициях. Позиции появятся после завершения первых задач.</div>
		{:else if showChart && trendLines.length > 0}
			<!-- SVG Position Trend Chart -->
			<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
				<svg viewBox="0 0 {getChartDims().containerW} {getChartDims().containerH}" class="w-full overflow-visible" onmousemove={chartMouseMove}>
					{#const dims = getChartDims()}
					<!-- Grid lines (horizontal) -->
					{#for (let i = 1; i <= Math.min(10, Math.floor(dims.innerH / 30)); i++)}
						<line x1={dims.marginL} y1={dims.marginT + (i / Math.min(10, Math.floor(dims.innerH / 30))) * dims.innerH} x2={dims.marginL + dims.innerW} y2={dims.marginT + (i / Math.min(10, Math.floor(dims.innerH / 30))) * dims.innerH} stroke="#f1f5f9" stroke-width="1" />
					{/for}

					<!-- Axis labels -->
					<text x={dims.marginL - 8} y={dims.marginT + 12} text-anchor="end" fill="#94a3b8" font-size="10">#{Math.max(1, Math.min(...trendLines[0].data.map((d: any) => d.position)) || 1)}</text>
					<text x={dims.marginL - 8} y={dims.marginT + dims.innerH + 4} text-anchor="end" fill="#94a3b8" font-size="10">#{20}</text>

					<!-- X-axis date labels -->
					{#if trendLines[0]?.data?.length > 0}
						{#for (let i = 0; i < trendLines[0].data.length; i += Math.max(1, Math.floor(trendLines[0].data.length / 6)))}
							<text x={dims.marginL + (i / (trendLines[0].data.length - 1 || 1)) * dims.innerW} y={dims.marginT + dims.innerH + 24} text-anchor="middle" fill="#94a3b8" font-size="9">{new Date(trendLines[0].data[i].date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}</text>
						{/for}
					{/if}

					<!-- Trend lines -->
					{#each trendLines as line}
						<text x={dims.marginL - 8} y={dims.marginT + 4 + trendLines.indexOf(line) * 12} text-anchor="end" fill={chartHoverQuery === line.text ? '#3b82f6' : '#64748b'} font-size="9" font-weight={chartHoverQuery === line.text ? '600' : '400'}>{line.text}</text>
					{/each}

					<!-- Paths -->
					<path d="{buildChartPath(trendLines)}" fill="none" stroke-width="2" stroke="#3b82f6" opacity="0.6" />

					<!-- Hover line and tooltip -->
					{#if hoverDate && trendLines[0]?.data?.length > 0}
						{#const hoverIdx = trendLines[0].data.findIndex((d: any) => d.date === hoverDate)}
						{#if hoverIdx >= 0}
							<line x1={dims.marginL + (hoverIdx / (trendLines[0].data.length - 1 || 1)) * dims.innerW} y1={dims.marginT} x2={dims.marginL + (hoverIdx / (trendLines[0].data.length - 1 || 1)) * dims.innerW} y2={dims.marginT + dims.innerH} stroke="#3b82f6" stroke-width="1" stroke-dasharray="4,4" opacity="0.5" />
						{/if}
					{/if}
				
				</svg>

				<!-- Legend -->
				<div class="mt-3 flex flex-wrap gap-x-4 gap-y-1">
					{#each trendLines as line}
						<button onclick={() => { chartHoverQuery = chartHoverQuery === line.text ? null : line.text; }} class="flex items-center gap-1.5 text-xs hover:opacity-80 transition-opacity" onmouseleave={() => { chartHoverQuery = null; }}>
							<span class="w-2 h-2 rounded-full bg-blue-500"></span>
							<span class="text-gray-600 truncate max-w-[120px]">{line.text}</span>
						</button>
					{/each}
				</div>

				{#if hoverDate && trendLines.length > 0}
					<div class="mt-3 p-3 bg-gray-50 rounded-lg text-xs space-y-1">
						<p class="font-medium text-gray-700">{new Date(hoverDate).toLocaleDateString('ru-RU')}</p>
						{#each trendLines as line}
							{#const d = line.data.find((p: any) => p.date === hoverDate)}
							{#if d}
								<div class="flex justify-between gap-4">
									<span class="text-gray-500 truncate">{line.text}</span>
									<span class="font-mono font-medium text-blue-600">#{d.position}</span>
								</div>
							{/if}
						{/each}
					</div>
				{/if}
			</div>

		{:else if !showChart && positionsData.length > 0}
			<!-- Table view -->
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Запрос</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Позиция</th>
							</tr>
						</thead>
						<tbody>
							{#each positionsData as pos}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-medium text-gray-900">{pos.text}</td>
									<td class="px-4 py-3">
										<span class={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
											pos.position <= 3 ? 'bg-green-100 text-green-800' :
											pos.position <= 10 ? 'bg-blue-100 text-blue-800' :
											'bg-gray-100 text-gray-800'
										}`}>#{pos.position}</span>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{:else if activeTab === 'delegates'}
		<!-- Delegates tab -->
		<div class="mb-4">
			<p class="text-sm text-gray-500">Управление доступом к проекту для других пользователей.</p>
		</div>

		<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm mb-6">
			<h3 class="text-sm font-medium text-gray-900 mb-3">Добавить делегата</h3>
			<div class="flex flex-wrap gap-2 items-end">
				<div>
					<label class="block text-xs text-gray-500 mb-1">ID пользователя</label>
					<input type="text" bind:value={newDelegateUserId} placeholder="uuid" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none w-72" />
				</div>
				<div>
					<label class="block text-xs text-gray-500 mb-1">Роль</label>
					<select bind:value={newDelegateRole} class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
						<option value="view">Только просмотр</option>
						<option value="edit">Просмотр и редактирование</option>
					</select>
				</div>
				<button onclick={addDelegate} class="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">Добавить</button>
			</div>
		</div>

		{#if delegates.length === 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">Нет делегатов. Добавьте пользователей для совместного доступа к проекту.</div>
		{:else}
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">UserID</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Роль</th>
								<th class="px-4 py-3 text-right font-medium text-gray-600">Действия</th>
							</tr>
						</thead>
						<tbody>
							{#each delegates as d}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-mono text-xs text-gray-700">{d.delegate_user_id}</td>
									<td class="px-4 py-3">
										<span class={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
											d.role === 'edit' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
										}`}>{d.role === 'edit' ? 'Редактирование' : 'Только просмотр'}</span>
									</td>
									<td class="px-4 py-3 text-right">
										<button onclick={() => removeDelegate(d.delegate_user_id)} class="text-red-500 hover:text-red-700 text-xs">Удалить</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

	{:else if activeTab === 'markers'}
		<!-- Markers tab -->
		<div class="mb-4">
			<p class="text-sm text-gray-500">Визуальные маркеры для отслеживания страниц сайта</p>
		</div>

		<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm mb-6">
			<h3 class="text-sm font-medium text-gray-900 mb-3">Добавить маркер</h3>
			<div class="flex flex-wrap gap-2">
				<input type="text" bind:value={newMarkerName} placeholder="Название" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none flex-1 min-w-[150px]" />
				<input type="url" bind:value={newMarkerUrl} placeholder="URL страницы" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none flex-1 min-w-[200px]" />
				<input type="text" bind:value={newMarkerSelector} placeholder="CSS селектор (опционально)" class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none flex-1 min-w-[200px]" />
				<button onclick={addMarker} class="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">Добавить</button>
			</div>
		</div>

		{#if markersData.length === 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">Нет маркеров. Добавьте первый маркер для начала работы.</div>
		{:else}
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Название</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">URL</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">CSS селектор</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Статус</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Действия</th>
							</tr>
						</thead>
						<tbody>
							{#each markersData as marker}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-medium text-gray-900">{marker.name}</td>
									<td class="px-4 py-3 text-blue-600 truncate max-w-[200px]"><a href={marker.url} target="_blank" class="hover:underline">{marker.url}</a></td>
									<td class="px-4 py-3 text-gray-600 font-mono text-xs">{marker.css_selector || '—'}</td>
									<td class="px-4 py-3">
										<span class={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${marker.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
											{marker.is_active ? 'Активен' : 'Неактивен'}
										</span>
									</td>
									<td class="px-4 py-3">
										<button onclick={() => deleteMarker(marker.id)} class="text-red-500 hover:text-red-700 text-xs">Удалить</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

	{:else if activeTab === 'webmaster'}
		<!-- Webmaster tab -->
		<div class="mb-4">
			<p class="text-sm text-gray-500">Верификация домена через Яндекс.Вебмастер, Google Search Console и другие сервисы</p>
		</div>

		<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm mb-6">
			<h3 class="text-sm font-medium text-gray-900 mb-3">Добавить сервис верификации</h3>
			<div class="flex gap-2">
				<button onclick={() => addWebmarker('yandex')} class="px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg text-sm font-medium transition-colors">Яндекс.Вебмастер</button>
				<button onclick={() => addWebmarker('google')} class="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg text-sm font-medium transition-colors">Google Search Console</button>
			</div>
		</div>

		{#if webmarkersData.length === 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">Нет подключённых сервисов. Добавьте первый для верификации домена.</div>
		{:else}
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Платформа</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Код верификации</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Статус</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Последняя синхронизация</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Действия</th>
							</tr>
						</thead>
						<tbody>
							{#each webmarkersData as wm}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-medium text-gray-900 capitalize">{wm.platform}</td>
									<td class="px-4 py-3 font-mono text-xs">{wm.verification_code || '—'}</td>
									<td class="px-4 py-3">
										<span class={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${wm.is_verified ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
											{wm.is_verified ? 'Верифицирован' : 'Ожидает'}
										</span>
									</td>
									<td class="px-4 py-3 text-gray-500 text-xs">{wm.last_sync ? new Date(wm.last_sync).toLocaleString('ru-RU') : '—'}</td>
									<td class="px-4 py-3 flex gap-2">
										{#if !wm.is_verified}
											<button onclick={() => verifyWebmarker(wm.id)} class="text-green-500 hover:text-green-700 text-xs">Верифицировать</button>
										{/if}
										<button onclick={() => deleteWebmarker(wm.id)} class="text-red-500 hover:text-red-700 text-xs">Удалить</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{:else if activeTab === 'settings'}
			<!-- Settings tab: integrations, schedule window, query modifications -->
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
				<h3 class="text-lg font-semibold text-gray-900 mb-4">Настройки проекта</h3>

				{#if settingsSaved}
					<div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">Настройки сохранены</div>
				{/if}

				<!-- Integration selector -->
				<div class="mb-6">
					<label class="block text-sm font-medium text-gray-700 mb-1">Интеграция</label>
					<select bind:value={settingIntegration} class="w-full max-w-md px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
						<option value="default">Default (без интеграции)</option>
						<option value="integration_2">Integration 2</option>
						<option value="integration_1_testing">Integration 1 (testing)</option>
						<option value="main_bay_belarus">Main Bay Belarus</option>
					</select>
				</div>

				<!-- Schedule window -->
				<div class="mb-6">
					<label class="block text-sm font-medium text-gray-700 mb-2">Окно расписания</label>
					<div class="grid grid-cols-2 gap-3 max-w-sm">
						<div>
							<label class="block text-xs text-gray-500 mb-1">Начало</label>
							<input type="time" bind:value={settingScheduleStart} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
						<div>
							<label class="block text-xs text-gray-500 mb-1">Окончание</label>
							<input type="time" bind:value={settingScheduleEnd} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
					</div>
				</div>

				<!-- Query modifications -->
				<div class="mb-6">
					<label class="block text-sm font-medium text-gray-700 mb-2">Модификации запросов</label>
					<div class="space-y-2 max-w-md">
						<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
							<input type="checkbox" bind:checked={settingModsCapital} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
							Каждый с заглавной буквы
						</label>
						<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
							<input type="checkbox" bind:checked={settingModsRandomCaps} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
							Случайные регистр букв (random-caps)
						</label>
						<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
							<input type="checkbox" bind:checked={settingModsTypos} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
							Ввод опечаток (typos)
						</label>
						<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
							<input type="checkbox" bind:checked={settingModsTrailingSpace} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
							Trailing space (пробел в конце)
						</label>
					</div>
				</div>

				<button onclick={saveProjectSettings} disabled={settingsSaving} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors">
					{settingsSaving ? 'Сохранение…' : 'Сохранить настройки'}
				</button>
			</div>

		{/if}
{/if}
</div>

<!-- Proklik modal -->
{#if showProklik && project}
<div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onclick={(e) => { if (e.target === e.currentTarget) showProklik = false; }}>
	<div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-md m-4">
		<h3 class="text-lg font-semibold text-gray-900 mb-4">Проклик — мгновенные клики</h3>

		{#if proklikMode === "all"}
			<p class="text-sm text-gray-600 mb-3">Отправить {proklikCount} проклик(ов) на случайные запросы проекта.</p>
			<label class="block text-sm font-medium text-gray-700 mb-1">Количество</label>
			<input type="number" bind:value={proklikCount} min="1" max="1000" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 outline-none" />
		{:else}
			<p class="text-sm text-gray-600 mb-3">Отправить проклики по выбранным запросам ({proklikQueries.length шт.}).</p>
			<label class="block text-sm font-medium text-gray-700 mb-1">Кликов на каждый запрос</label>
			<input type="number" bind:value={proklikCount} min="1" max="100" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-purple-500 outline-none" />
		{/if}

		<div class="flex justify-end gap-2 mt-5">
			<button onclick={() => showProklik = false} class="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors">Отмена</button>
			<button onclick={sendProklik} disabled={proklikLoading} class="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 text-white rounded-lg text-sm font-medium transition-colors">
				{proklikLoading ? 'Отправка…' : 'Отправить проклик'}
			</button>
		</div>
	</div>
</div>
{/if}

<!-- Boost modal -->
{#if showBoost && project}
<div class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onclick={(e) => { if (e.target === e.currentTarget) showBoost = false; }}>
	<div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg m-4">
		<h3 class="text-lg font-semibold text-gray-900 mb-1">Буст — ускоренный прогон</h3>
		<p class="text-sm text-gray-500 mb-4">Выбранные: {selectedQueryIds.size} запросов</p>

		<div class="space-y-3">
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1">Кликов в день на каждый запрос</label>
				<input type="number" bind:value={boostDailyClicks} min="1" max="10000" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500 outline-none" />
			</div>
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1">Интервал между кликами (секунды)</label>
				<input type="number" bind:value={boostInterval} min="60" max="86400" step="60" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-orange-500 outline-none" />
				<p class="text-xs text-gray-400 mt-1">Минимум 60 секунд. Например, 3600 = 1 клик/час</p>
			</div>

			<!-- Boost schedule window -->
			<div class="border-t border-gray-200 pt-3 mt-3">
				<p class="text-sm font-medium text-gray-700 mb-2">Окно расписания буста</p>
				<div class="grid grid-cols-2 gap-3">
					<div>
						<label class="block text-xs text-gray-500 mb-1">Начало</label>
						<input type="time" bind:value={boostScheduleStart} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 outline-none" />
					</div>
					<div>
						<label class="block text-xs text-gray-500 mb-1">Окончание</label>
						<input type="time" bind:value={boostScheduleEnd} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 outline-none" />
					</div>
				</div>
			</div>

			<!-- Day distribution -->
			<div class="border-t border-gray-200 pt-3">
				<p class="text-sm font-medium text-gray-700 mb-2">Распределение по дням недели</p>
				<p class="text-xs text-gray-500 mb-2">Выберите дни для буста (оставьте пустым — каждый день)</p>
				<div class="flex gap-2 flex-wrap">
					{#each dayLabels as day}
						<button onclick={() => boostDayDist[day.key] = !boostDayDist[day.key]} class={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${boostDayDist[day.key] ? 'bg-orange-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
							{day.label}
						</button>
					{/each}
				</div>
			</div>

			<div class="flex items-center gap-2">
				<input type="checkbox" bind:checked={boostStartFromNow} id="boost_now" class="rounded border-gray-300 text-orange-600 focus:ring-orange-500" />
				<label for="boost_now" class="text-sm text-gray-700">Начать расписание с сейчас, иначе — с завтра</label>
			</div>
		</div>

		<div class="flex justify-end gap-2 mt-5">
			<button onclick={() => showBoost = false} class="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 transition-colors">Отмена</button>
			<button onclick={sendBoost} disabled={boostLoading || selectedQueryIds.size === 0} class="px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors">
				{boostLoading ? 'Буст...' : `Запустить буст (${selectedQueryIds.size} запросов)`}
			</button>
		</div>
	</div>
</div>
{/if}


<!-- Daily drill-down modal -->
{#if showDrillDown}
<div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50" onclick={(e) => { if (e.target === e.currentTarget) showDrillDown = false; }}>
<div class="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
	<div class="flex items-center justify-between p-4 border-b border-gray-200">
		<h3 class="text-lg font-semibold text-gray-900">&#1040;&#1083;&#1086;&#1090;&#1077;&#1083;&#1103; &#1087;&#1088;&#1080; {drillDate}</h3>
		<button onclick={() => showDrillDown = false} class="text-gray-400 hover:text-gray-600">&times;</button>
	</div>
	<div class="p-4 overflow-y-auto max-h-[calc(90vh-80px)]">
		{#if drillLoading}
			<p class="text-sm text-gray-500 text-center py-8">&#1053;&#1072; &#1085;&#1072;&#1089;&#1097;&#1072;&#1085;&#1080;&#1077;...</p>
		{:else}
			<p class="text-sm text-gray-600 mb-3">&#1053;&#1086;&#1075;&#1084;&#1072; &#1085;&#1090;&#1086;&#1074;&#1086;&#1084;: <strong>{drillClicks.length}</strong></p>
			{#if drillClicks.length === 0}
				<p class="text-sm text-gray-500 text-center py-4">&#1057;&#1072;&#1079;&#1084;&#1086;&#1090;&#1090;&#1072; &#1074;&#1085;&#1077;&#1078;&#1085;&#1077;&#1075;&#1086;</p>
			{:else}
				<div class="space-y-2">
					{#each drillClicks as click}
						<div class="border border-gray-200 rounded-lg p-3 hover:bg-gray-50 transition-colors cursor-pointer" onclick={() => openTaskDetail(click.id)}>
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0 flex-1">
									<p class="text-sm text-gray-900 truncate">{click.url}</p>
									<div class="flex items-center gap-2 mt-1">
										<span class="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-blue-50 text-blue-700">{statusLabels[click.source] || click.source}</span>
										<span class="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium {click.status === &#x27;completed&#x27; ? &#x27;bg-green-50 text-green-700&#x27; : click.status === &#x27;not_found&#x27; ? &#x27;bg-red-50 text-red-700&#x27; : &#x27;bg-yellow-50 text-yellow-700&#x27;}">{statusLabels[click.status] || click.status}</span>
										{#if click.position}
											<span class="text-xs text-gray-500">&#1055;&#1086;&#1076;: {click.position}</span>
											{/if}
									</div>
								</div>
								<span class="text-xs text-gray-400 whitespace-nowrap">{click.created_at ? new Date(click.created_at).toLocaleTimeString(&#x27;ru-RU&#x27;) : &#x27;&#x27;}</span>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	</div>
</div>
</div>
{/if}
<!-- Bulk Edit Modal -->
{#if showBulkEdit}
<div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50" onclick={(e) => { if (e.target === e.currentTarget) showBulkEdit = false; }}>
<div class="bg-white rounded-xl shadow-2xl max-w-lg w-full m-4 max-h-[90vh] overflow-y-auto">
	<div class="flex items-center justify-between p-4 border-b border-gray-200">
		<h3 class="text-lg font-semibold text-gray-900">Массовое редактирование ({selectedQueryIds.size})</h3>
		<button onclick={() => showBulkEdit = false} class="text-gray-400 hover:text-gray-600">&times;</button>
	</div>
	<div class="p-4 space-y-4">
		<div>
			<label class="block text-sm font-medium text-gray-700 mb-1">Кликов/день (новое значение)</label>
			<input type="number" bind:value={bulkEditDailyClicks} min="0" placeholder="Не менять" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
			<p class="text-xs text-gray-400 mt-1">Установите значение для изменения daily_clicks у выбранных запросов</p>
		</div>
		<div>
			<label class="block text-sm font-medium text-gray-700 mb-1">Гео (JSON, опционально)</label>
			<textarea bind:value={bulkEditGeoJson} rows="3" placeholder='{"country": "ru"}' class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-indigo-500 outline-none" />
			<p class="text-xs text-gray-400 mt-1">Заменит geo у выбранных запросов (должен быть валидным JSON)</p>
		</div>
		<div>
			<label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
				<input type="checkbox" bind:checked={bulkEditApplyClickUrlToggle} class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500" />
				Установить click_url для выбранных запросов
			</label>
			{#if bulkEditApplyClickUrlToggle}
				<input type="url" bind:value={bulkEditApplyClickUrl} placeholder="https://example.com/click" class="mt-2 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 outline-none" />
			{/if}
		</div>
		<div class="flex gap-2 pt-2">
			<button onclick={() => showBulkEdit = false} class="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors">Отмена</button>
			<button onclick={bulkUpdate} disabled={bulkLoading} class="flex-1 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white rounded-lg text-sm font-medium transition-colors">
				{bulkLoading ? 'Обновление...' : 'Обновить'}
			</button>
		</div>
	</div>
</div>
</div>
{/if}
