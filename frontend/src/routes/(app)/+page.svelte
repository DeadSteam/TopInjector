<script lang="ts">
	import "../app.css";
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	interface ProjectGroup {
		id: string;
		name: string;
		icon: string;
	}

	interface Project {
		id: string;
		name: string;
		domain: string;
		region: string;
		strategy_type: string;
		daily_limit: number;
		is_active: boolean;
		group_id: string | null;
		query_count: number;
		clicks_done?: number;
		queue_pending?: number;
		not_found?: number;
		stuck?: number;
		is_delegate?: boolean;
	}

	let projects = $state<Project[]>([]);
	let groups = $state<ProjectGroup[]>([]);
	let loading = $state(true);
	let error = $state("");

	// Filters & search
	let searchQuery = $state("");
	let filterGroup = $state<string>("all");
	let filterRegion = $state<string>("all");
	let filterStrategy = $state<string>("all");
	let filterActive = $state<string>("all");

	// Column visibility
	let showRegionCol = $state(true);
	let showStrategyCol = $state(true);
	let showLimitCol = $state(false);
	let showQueriesCol = $state(false);
	let showQueueCol = $state(false);
	let showNotFoundCol = $state(false);
	let showStuckCol = $state(false);
	let showActionsCol = $state(true);
	let showActiveToggle = $state(true);

	// Source breakdown columns
	let showSourceBreakdown = $state(false);
	let sourceData: Record<string, { completed_by_source: Record<string, number>; pending_by_source: Record<string, number> }> = {};
	let sourceLoading = $state(false);

	// Overdue filter
	let showOverdueOnly = $state(false);

	let searchDebounce: number | null = null;
	let autoRefreshId: number | null = null;

	// Modals
	let showCreateModal = $state(false);
	let showGroupModal = $state(false);
	let editingGroup = $state<ProjectGroup | null>(null);
	let createFormName = $state("");
	let createFormDomain = $state("");
	let createFormRegion = $state("");
	let createFormStrategy = $state("daily");
	let createFormGroupId = $state<string>("all");
	let createFormIntegration = $state("default");
	let createFormScheduleStart = $state("");
	let createFormScheduleEnd = $state("");
	let createFormModsCapital = $state(false);
	let createFormModsRandomCaps = $state(false);
	let createFormModsTypos = $state(false);
	let createFormModsTrailingSpace = $state(false);
	let groupName = $state("");
	let groupIcon = $state("");

	// Context menu
	let contextMenu = $state<{ x: number; y: number; projectId: string } | null>(null);
	let editingProjectId = $state<string | null>(null);

	async function loadData() {
		try {
			await Promise.all([loadGroups(), loadProjects()]);
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	async function loadGroups() {
		try {
			groups = await api.groups.list();
		} catch {
			groups = [];
		}
	}

	// Pagination
	let currentPage = $state(1);
	let pageSize = $state(20);
	let totalProjects = $state(0);
	let totalFiltered = $state<number | null>(null);

	async function loadProjects() {
		const params: any = {};
		if (searchQuery) params.search = searchQuery;
		if (filterGroup !== "all") params.group_id = filterGroup;
		if (filterRegion !== "all") params.region = filterRegion;
		if (filterStrategy !== "all") params.strategy_type = filterStrategy;
		if (filterActive !== "all") params.is_active = filterActive === "true";
		params.page = currentPage;
		params.page_size = pageSize;

		try {
			const resp: any = await api.projects.list(params);
			projects = resp?.items ?? resp ?? [];
			totalProjects = resp?.total ?? projects.length;
			totalFiltered = resp?.total ?? null;
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки проектов";
			projects = [];
			totalProjects = 0;
		}
	}

	async function loadSourceBreakdowns() {
		if (!showSourceBreakdown || projects.length === 0) return;
		sourceLoading = true;
		try {
			const results = await Promise.allSettled(
				projects.map(p => api.projects.sourceBreakdown(p.id).catch(() => null))
			);
			sourceData = {};
			projects.forEach((p, i) => {
				if (results[i]?.status === 'fulfilled' && results[i].value) {
					sourceData[p.id] = results[i].value;
				}
			});
		} finally {
			sourceLoading = false;
		}
	}

	async function loadAllStats() {
		await loadProjects();
		if (showSourceBreakdown) await loadSourceBreakdowns();
	}

	async function loadOverdueCounts() {
		if (projects.length === 0 || !showOverdueOnly) return;
		const results = await Promise.allSettled(
			projects.map(p => api.projects.overdueCount(p.id).catch(() => ({ overdue: 0 })))
		);
		return Object.fromEntries(
			projects.map((p, i) => [p.id, results[i]?.status === 'fulfilled' ? (results[i].value as any).overdue : 0])
		);
	}

	async function toggleOverdue() {
		if (showOverdueOnly) {
			showOverdueOnly = false;
			await loadProjects();
		} else {
			showOverdueOnly = true;
			const counts = await loadOverdueCounts();
			projects = projects.filter(p => (counts as any)[p.id] > 0);
		}
	}

	function handleSearch() {
		if (searchDebounce) clearTimeout(searchDebounce);
		searchDebounce = window.setTimeout(() => { currentPage = 1; loadProjects(); }, 300);
	}

	function handleFilterResetPage() {
		currentPage = 1;
		loadProjects();
	}

	// Pagination helpers
	function goToPage(page: number) {
		currentPage = page;
		loadProjects();
	}

	const totalPages = $derived(Math.max(1, Math.ceil((totalFiltered ?? totalProjects) / pageSize)));
	const showPages = $derived(() => {
		// Show at most 7 page numbers
		const pages: number[] = [];
		const start = Math.max(1, currentPage - 3);
		const end = Math.min(totalPages, currentPage + 3);
		for (let i = start; i <= end; i++) pages.push(i);
		return pages;
	});

	async function createProject() {
		if (!createFormName || !createFormDomain) return;
		const data: any = {
			name: createFormName,
			domain: createFormDomain,
			strategy_type: createFormStrategy,
			daily_limit: 100,
			integrations: {},
			scheduling_window: null,
			query_modifications: {},
		};
		if (createFormRegion) data.region = createFormRegion;
		data.group_id = createFormGroupId === "all" ? null : createFormGroupId;

		// Integration
		if (createFormIntegration !== "default") {
			data.integrations.integration_type = createFormIntegration;
		}

		// Schedule window
		if (createFormScheduleStart && createFormScheduleEnd) {
			data.scheduling_window = { start: createFormScheduleStart, end: createFormScheduleEnd };
		}

		// Query modifications
		const mods: Record<string, boolean> = {};
		if (createFormModsCapital) mods.capital_first = true;
		if (createFormModsRandomCaps) mods.random_caps = true;
		if (createFormModsTypos) mods.typos = true;
		if (createFormModsTrailingSpace) mods.trailing_space = true;
		if (Object.keys(mods).length > 0) data.query_modifications = mods;

		try {
			await api.projects.create(data);
			showCreateModal = false;
			createFormName = ""; createFormDomain = ""; createFormRegion = "";
			createFormStrategy = "daily"; createFormGroupId = "all";
			createFormIntegration = "default";
			createFormScheduleStart = ""; createFormScheduleEnd = "";
			createFormModsCapital = false; createFormModsRandomCaps = false;
			createFormModsTypos = false; createFormModsTrailingSpace = false;
			await loadProjects();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка создания";
		}
	}

	async function toggleActive(id: string, active: boolean) {
		try {
			await api.projects.activate(id, !active);
			await loadProjects();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка переключения";
		}
	}

	async function deleteProject(id: string) {
		if (!confirm("Удалить проект?")) return;
		try {
			await api.projects.delete(id);
			await loadProjects();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка удаления";
		}
	}

	function showContextMenu(e: MouseEvent, projectId: string) {
		e.preventDefault();
		contextMenu = { x: e.clientX, y: e.clientY, projectId };
	}

	document.addEventListener("click", () => { contextMenu = null; });

	async function copyProject(id: string) {
		const proj = projects.find(p => p.id === id);
		if (!proj) return;
		try {
			await api.projects.create({
				name: proj.name + " (копия)",
				domain: proj.domain,
				region: proj.region,
				strategy_type: proj.strategy_type,
				daily_limit: proj.daily_limit,
			});
			await loadProjects();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка копирования";
		}
	}

	function editProject(id: string) {
		const proj = projects.find(p => p.id === id);
		if (!proj) return;
		editingProjectId = id;
		createFormName = proj.name;
		createFormDomain = proj.domain;
		createFormRegion = proj.region || "";
		createFormStrategy = proj.strategy_type || "daily";

		// Load full project details for advanced fields
		api.projects.get(id).then(full => {
			if (full.integrations) createFormIntegration = full.integrations.integration_type || "default";
			if (full.scheduling_window) {
				createFormScheduleStart = full.scheduling_window.start || "";
				createFormScheduleEnd = full.scheduling_window.end || "";
			}
			if (full.query_modifications) {
				createFormModsCapital = !!full.query_modifications.capital_first;
				createFormModsRandomCaps = !!full.query_modifications.random_caps;
				createFormModsTypos = !!full.query_modifications.typos;
				createFormModsTrailingSpace = !!full.query_modifications.trailing_space;
			}
		}).catch(() => { /* fallback to defaults */ });
	}

	async function saveEdit() {
		if (!editingProjectId || !createFormName || !createFormDomain) return;
		const proj = projects.find(p => p.id === editingProjectId);
		if (!proj) return;
		const data: any = {
			name: createFormName,
			domain: createFormDomain,
			region: createFormRegion || undefined,
			strategy_type: createFormStrategy,
		};

		// Integration
		data.integrations = {};
		if (createFormIntegration !== "default") data.integrations.integration_type = createFormIntegration;

		// Schedule window
		if (createFormScheduleStart && createFormScheduleEnd) {
			data.scheduling_window = { start: createFormScheduleStart, end: createFormScheduleEnd };
		} else {
			data.scheduling_window = null;
		}

		// Query modifications
		const mods: Record<string, boolean> = {};
		if (createFormModsCapital) mods.capital_first = true;
		if (createFormModsRandomCaps) mods.random_caps = true;
		if (createFormModsTypos) mods.typos = true;
		if (createFormModsTrailingSpace) mods.trailing_space = true;
		data.query_modifications = mods;

		try {
			await api.projects.update(editingProjectId, data);
			editingProjectId = null;
			await loadProjects();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка сохранения";
		}
	}

	async function saveGroup() {
		if (!groupName.trim()) return;
		try {
			if (editingGroup) {
				await api.groups.update(editingGroup.id, { name: groupName, icon: groupIcon });
			} else {
				await api.groups.create({ name: groupName, icon: groupIcon || "" });
			}
			showGroupModal = false;
			groupName = ""; groupIcon = ""; editingGroup = null;
			await loadGroups();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка группы";
		}
	}

	async function deleteGroup(id: string) {
		if (!confirm("Удалить группу?")) return;
		try {
			await api.groups.delete(id);
			await loadGroups();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка удаления группы";
		}
	}

	function openNewGroup() {
		editingGroup = null;
		groupName = ""; groupIcon = "";
		showGroupModal = true;
	}

	function editGroup(group: ProjectGroup) {
		editingGroup = group;
		groupName = group.name;
		groupIcon = group.icon || "";
		showGroupModal = true;
	}

	// Available regions from projects data
	const allRegions = $derived([...new Set(projects.map(p => p.region).filter(Boolean))]);
	const strategies = ["all", "daily", "monthly", "hourly"];

	// Toggle column visibility
	function toggleCol(col: string) {
		switch (col) {
			case 'region': showRegionCol = !showRegionCol; break;
			case 'strategy': showStrategyCol = !showStrategyCol; break;
			case 'limit': showLimitCol = !showLimitCol; break;
			case 'queries': showQueriesCol = !showQueriesCol; break;
			case 'queue': showQueueCol = !showQueueCol; break;
			case 'not_found': showNotFoundCol = !showNotFoundCol; break;
			case 'stuck': showStuckCol = !showStuckCol; break;
		}
	}

	function toggleSourceBreakdown() {
		showSourceBreakdown = !showSourceBreakdown;
		if (showSourceBreakdown) loadSourceBreakdowns();
		else sourceData = {};
	}

	let hasOverdueProjects = $derived(
		projects.some(p => {
			const sb = sourceData[p.id];
			return sb && (sb.pending_by_source.strategy > 0 || sb.pending_by_source.autoburst > 0);
		})
	);

	onMount(() => {
		loadData();
		autoRefreshId = window.setInterval(loadProjects, 30000); // poll every 30s
	});

	onDestroy(() => {
		if (searchDebounce) clearTimeout(searchDebounce);
		if (autoRefreshId) clearInterval(autoRefreshId);
	});

	const filteredGroups = $derived(groups.filter(g => g.name.toLowerCase().includes(filterGroup.toLowerCase())));
</script>

<div class="p-6 max-w-[1600px]">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6 flex-wrap gap-4">
		<h1 class="text-2xl font-bold text-gray-900">Проекты</h1>
		<div class="flex items-center gap-3">
			<button onclick={openNewGroup} class="px-3 py-2 bg-gray-700 hover:bg-gray-800 text-white text-sm rounded-lg transition-colors">
				+ Группа
			</button>
			<button onclick={() => showCreateModal = true} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors">
				+ Создать проект
			</button>
		</div>
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
			{error}
			<button onclick={() => error = ""} class="ml-2 text-red-800 hover:text-red-900">×</button>
		</div>
	{/if}

	<!-- Search & Filters -->
	<div class="mb-4 flex flex-wrap gap-3 items-center">
		<input
			bind:value={searchQuery}
			oninput={handleSearch}
			placeholder="Поиск проектов..."
			class="flex-1 min-w-[200px] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
		/>

		<select bind:value={filterGroup} onchange={handleFilterResetPage} class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
			<option value="all">Все группы</option>
			{#each groups as group}
				<option value={group.id}>{group.name}</option>
			{/each}
		</select>

		<select bind:value={filterRegion} onchange={handleFilterResetPage} class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
			<option value="all">Все регионы</option>
			{#each allRegions as region}
				<option value={region}>{region}</option>
			{/each}
		</select>

		<select bind:value={filterStrategy} onchange={handleFilterResetPage} class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
			{#each strategies as s}
				<option value={s}>{s === "all" ? "Все стратегии" : s}</option>
			{/each}
		</select>

		<select bind:value={filterActive} onchange={handleFilterResetPage} class="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
			<option value="all">Все</option>
			<option value="true">Активные</option>
			<option value="false">Неактивные</option>
		</select>

		<!-- Column config -->
		<div class="relative">
			<button onclick={() => toggleCol('region')} class={`px-2 py-1 text-xs border rounded-lg transition-colors ${showRegionCol ? 'bg-green-50 text-green-700 border-green-300' : 'text-gray-400 border-gray-300'}`}>
				Регион {showRegionCol ? '✓' : ''}
			</button>
			<button onclick={() => toggleCol('strategy')} class={`px-2 py-1 text-xs border rounded-lg transition-colors ${showStrategyCol ? 'bg-green-50 text-green-700 border-green-300' : 'text-gray-400 border-gray-300'}`}>
				Стратегия {showStrategyCol ? '✓' : ''}
			</button>
			<button onclick={() => toggleCol('limit')} class={`px-2 py-1 text-xs border rounded-lg transition-colors ${showLimitCol ? 'bg-green-50 text-green-700 border-green-300' : 'text-gray-400 border-gray-300'}`}>
				Лимит {showLimitCol ? '✓' : ''}
			</button>
			<button onclick={() => toggleCol('queries')} class={`px-2 py-1 text-xs border rounded-lg transition-colors ${showQueriesCol ? 'bg-green-50 text-green-700 border-green-300' : 'text-gray-400 border-gray-300'}`}>
				Запросы {showQueriesCol ? '✓' : ''}
			</button>
		</div>
	</div>

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}
		<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 border-b border-gray-200">
						<tr>
							<th class="px-4 py-3 text-left font-medium text-gray-600 w-10"></th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Название</th>
							{#if showRegionCol}
								<th class="px-4 py-3 text-left font-medium text-gray-600">Регион</th>
							{/if}
							{#if showStrategyCol}
								<th class="px-4 py-3 text-left font-medium text-gray-600">Стратегия</th>
							{/if}
							<th class="px-4 py-3 text-left font-medium text-gray-600">Домен</th>
							{#if showLimitCol}
								<th class="px-4 py-3 text-left font-medium text-gray-600">Лимит/день</th>
							{/if}
							{#if showQueriesCol}
								<th class="px-4 py-3 text-left font-medium text-gray-600">Запросов</th>
							{/if}
							{#if showSourceBreakdown}
								<th class="px-4 py-3 text-left font-medium text-purple-600">Клики (стратегия)</th>
								<th class="px-4 py-3 text-left font-medium text-purple-600">Клики (автобёрст)</th>
								<th class="px-4 py-3 text-left font-medium text-purple-600">Клики (проклик)</th>
							{/if}
							{#if showActionsCol}
								<th class="px-4 py-3 text-right font-medium text-gray-600">Действия</th>
							{/if}
						</tr>
					</thead>
					<tbody>
						{#each projects as project (project.id)}
							<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
								<!-- Active toggle -->
								<td class="px-4 py-3">
									{#if showActiveToggle}
										<label class="inline-flex items-center cursor-pointer">
											<input type="checkbox" checked={project.is_active} onchange={() => toggleActive(project.id, project.is_active)} class="sr-only peer">
											<div class="relative w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-green-600"></div>
										</label>
									{/if}
								</td>
								<td class="px-4 py-3">
									<a href="/projects/{project.id}" class="font-medium text-blue-600 hover:text-blue-700 flex items-center gap-1.5">
										{#if project.is_delegate}
											<span class="w-2 h-2 rounded-full bg-yellow-400" title="Делегированный доступ"></span>
										{/if}
										{project.name}
									</a>
								</td>
								<!-- Region -->
								{#if showRegionCol}
									<td class="px-4 py-3 text-gray-600">{project.region || '—'}</td>
								{/if}
								<!-- Strategy -->
								{#if showStrategyCol}
									<td class="px-4 py-3">
										<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium
											{project.strategy_type === 'daily' ? 'bg-blue-100 text-blue-800' : project.strategy_type === 'monthly' ? 'bg-purple-100 text-purple-800' : 'bg-green-100 text-green-800'}">
											{project.strategy_type}
										</span>
									</td>
								{/if}
								<!-- Domain -->
								<td class="px-4 py-3 text-blue-600 truncate max-w-[200px]">
									<a href={project.domain} target="_blank" class="hover:underline">{project.domain}</a>
								</td>
								<!-- Limit -->
								{#if showLimitCol}
									<td class="px-4 py-3 text-gray-600">{project.daily_limit}</td>
								{/if}
								<!-- Query count -->
								{#if showQueriesCol}
									<td class="px-4 py-3 text-gray-600">{project.query_count || 0}</td>
								{/if}
								<!-- Source breakdown -->
								{#if showSourceBreakdown}
									{#let sb = sourceData[project.id]}
										<td class="px-4 py-3 text-green-600 font-medium">
											{sb?.completed_by_source.strategy ?? '—'}
										</td>
										<td class="px-4 py-3 text-blue-600 font-medium">
											{sb?.completed_by_source.autoburst ?? '—'}
										</td>
										<td class="px-4 py-3 text-purple-600 font-medium">
											{sb?.completed_by_source.proklik ?? '—'}
										</td>
									{/let}
								{/if}
								<!-- Actions -->
								{#if showActionsCol}
									<td class="px-4 py-3">
										<div class="flex items-center justify-end gap-2">
											<a href="/projects/{project.id}" class="text-blue-600 hover:text-blue-700 text-xs">Открыть</a>
											<button onclick={() => copyProject(project.id)} class="text-gray-500 hover:text-gray-700 text-xs">Копировать</button>
											<button onclick={() => deleteProject(project.id)} class="text-red-500 hover:text-red-700 text-xs">Удалить</button>
											<button onclick={showContextMenu} class="text-gray-400 hover:text-gray-600 text-xs">⋮</button>
										</div>
									</td>
								{/if}
							</tr>
						{:else}
							<tr>
								<td colspan="10" class="px-4 py-12 text-center text-gray-400">
									Нет проектов. {searchQuery ? 'Попробуйте изменить параметры поиска.' : 'Создайте первый проект для начала работы.'}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Pagination -->
			{#if totalPages > 1}
				<div class="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
					<p class="text-sm text-gray-500">
						Страница {currentPage} из {totalPages} · Всего {totalFiltered ?? totalProjects} проектов
					</p>
					<div class="flex items-center gap-1">
						<button
							onclick={() => goToPage(currentPage - 1)}
							disabled={currentPage <= 1}
							class="px-2 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
						>
						← Назад
						</button>
						{#each showPages() as page}
							<button
								onclick={() => goToPage(page)}
								class={`${page === currentPage ? 'bg-blue-600 text-white' : 'border hover:bg-gray-50'}`}
							>
								{page}
							</button>
						{/each}
						<button
							onclick={() => goToPage(currentPage + 1)}
							disabled={currentPage >= totalPages}
							class="px-2 py-1 text-sm border rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
						>
							Вперёд →
						</button>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Context menu -->
	{#if contextMenu}
		<div class="fixed z-50" style="left: {contextMenu.x}px; top: {contextMenu.y}px">
			<div class="bg-white border border-gray-200 rounded-lg shadow-lg py-1 w-56">
				<a href="/projects/{contextMenu.projectId}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">Открыть</a>
				<button onclick={() => { editProject(contextMenu.projectId); contextMenu = null; }} class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">Редактировать</button>
				<div class="my-1 border-t border-gray-100"></div>
				<button onclick={async () => { const p = projects.find(x => x.id === contextMenu.projectId); if (p) await toggleActive(contextMenu.projectId, p.is_active); contextMenu = null; }} class="w-full text-left px-4 py-2 text-sm {projects.find(x => x.id === contextMenu.projectId)?.is_active ? 'text-orange-600 hover:bg-orange-50' : 'text-green-600 hover:bg-green-50'}">{projects.find(x => x.id === contextMenu.projectId)?.is_active ? 'Остановить' : 'Запустить'}</button>
				<button onclick={async () => { await copyProject(contextMenu.projectId); contextMenu = null; }} class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">Копировать (с запросами)</button>
				<div class="my-1 border-t border-gray-100"></div>
				<button onclick={async () => { await deleteProject(contextMenu.projectId); contextMenu = null; }} class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50">Удалить</button>
			</div>
		</div>
	{/if}

	<!-- Create project modal -->
	{#if showCreateModal}
		<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onmousedown={(e) => e.target === e.currentTarget && (showCreateModal = false)}>
			<div class="bg-white rounded-xl shadow-2xl w-full max-w-lg p-6 m-4">
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-lg font-semibold text-gray-900">Создать проект</h2>
					<button onmousedown={(e) => { e.stopPropagation(); showCreateModal = false; }} class="text-gray-400 hover:text-gray-600">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>

				<form onsubmit={(e) => { e.preventDefault(); createProject(); }} class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Название проекта</label>
						<input type="text" bind:value={createFormName} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="Мой проект" required />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Домен</label>
						<input type="url" bind:value={createFormDomain} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="https://example.com" required />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Регион</label>
						<input type="text" bind:value={createFormRegion} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="Москва" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Стратегия распределения</label>
						<select bind:value={createFormStrategy} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
							<option value="daily">Суточная (равномерно по дням)</option>
							<option value="monthly">Месячная</option>
							<option value="hourly">Часовая (равномерно по часам)</option>
						</select>
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Группа проекта</label>
						<select bind:value={createFormGroupId} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
							<option value="all">Без группы</option>
							{#each groups as group}
								<option value={group.id}>{group.name}</option>
							{/each}
						</select>
					</div>

					<!-- Integration selector -->
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Интеграция</label>
						<select bind:value={createFormIntegration} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
							<option value="default">Default (без интеграции)</option>
							<option value="integration_2">Integration 2</option>
							<option value="integration_1_testing">Integration 1 (testing)</option>
							<option value="main_bay_belarus">Main Bay Belarus</option>
						</select>
					</div>

					<!-- Schedule window -->
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Время начала (расписание)</label>
							<input type="time" bind:value={createFormScheduleStart} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Время окончания</label>
							<input type="time" bind:value={createFormScheduleEnd} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
						</div>
					</div>

					<!-- Query modifications -->
					<div class="border-t border-gray-200 pt-4 mt-2">
						<p class="text-sm font-medium text-gray-700 mb-2">Модификации запросов</p>
						<div class="space-y-2">
							<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
								<input type="checkbox" bind:checked={createFormModsCapital} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
								Каждый с заглавной буквы
							</label>
							<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
								<input type="checkbox" bind:checked={createFormModsRandomCaps} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
								Случайные регистр букв (random-caps)
							</label>
							<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
								<input type="checkbox" bind:checked={createFormModsTypos} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
								Ввод опечаток (typos)
							</label>
							<label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
								<input type="checkbox" bind:checked={createFormModsTrailingSpace} class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
								Трailing space (пробел в конце)
							</label>
						</div>
					</div>
				</form>

				<div class="flex justify-end gap-3 mt-6">
					<button onmousedown={(e) => { e.stopPropagation(); showCreateModal = false; }} class="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors">
						Отмена
					</button>
					<button type="submit" onclick={createProject} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
						Создать
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Group modal -->
	{#if showGroupModal}
		<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onmousedown={(e) => e.target === e.currentTarget && (showGroupModal = false)}>
			<div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 m-4">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">{editingGroup ? 'Редактировать группу' : 'Новая группа'}</h2>

				<form onsubmit={(e) => { e.preventDefault(); saveGroup(); }} class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Название</label>
						<input type="text" bind:value={groupName} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="Мои клиенты" required />
					</div>
				</form>

				<div class="flex justify-end gap-3 mt-6">
					{#if editingGroup}
						<button onclick={() => deleteGroup(editingGroup.id)} class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors">
							Удалить
						</button>
					{/if}
					<button onmousedown={(e) => { e.stopPropagation(); showGroupModal = false; }} class="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors">
						Отмена
					</button>
					<button type="submit" form="groupForm" onclick={saveGroup} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
						{editingGroup ? 'Сохранить' : 'Создать'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Groups panel -->
	<div class="mt-6 bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
		<h3 class="text-sm font-medium text-gray-900 mb-3">Группы проектов</h3>
		{#if groups.length === 0}
			<p class="text-sm text-gray-500">Нет групп. Создайте первую.</p>
		{:else}
			<div class="flex flex-wrap gap-2">
				{#each groups as group}
					<div class="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg">
						<span class="text-sm font-medium text-gray-900">{group.name}</span>
						<button onclick={() => editGroup(group)} class="text-gray-400 hover:text-gray-600 text-xs">✏️</button>
						<button onclick={() => deleteGroup(group.id)} class="text-gray-400 hover:text-red-600 text-xs">×</button>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
