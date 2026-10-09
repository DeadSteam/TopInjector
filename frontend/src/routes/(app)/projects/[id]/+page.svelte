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

	// Markers
	let markersData = $state<any[]>([]);
	let newMarkerName = $state("");
	let newMarkerUrl = $state("");
	let newMarkerSelector = $state("");

	// Webmarkers
	let webmarkersData = $state<any[]>([]);

	// Inline edit state
	let editingQueryId = $state<string | null>(null);
	let editingDailyClicks = $state(0);
	let editingGeo = $state("");
	let editingClickUrl = $state("");

	// Proklik modal
	let showProklik = $state(false);
	let proklikCount = $state(1);
	let proklikQueries: string[] = [];
	let proklikMode = $state<"all" | "selected">("all");
	let proklikLoading = $state(false);

	// Selection
	let selectedQueryIds = new Set<string>();

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
		if (queries.every(q => selectedQueryIds.has(q.id))) {
			selectedQueryIds.clear();
		} else {
			queries.forEach(q => selectedQueryIds.add(q.id));
		}
	}

	// Delete query
	async function deleteQuery(queryId: string) {
		if (!confirm("Удалить запрос?")) return;
		try {
			await api.projects.deleteQuery(projectId, queryId);
			await loadQueries();
			await loadQueueStats();
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка удаления запроса"; }
	}

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
		startAutoRefresh();
	}

	onDestroy(() => { stopAutoRefresh(); });

	const tabList = [
		{ key: "queries", label: "Запросы" },
		{ key: "queue", label: "Очередь" },
		{ key: "analytics", label: "Аналитика" },
		{ key: "positions", label: "Позиции" },
		{ key: "markers", label: "Маркеры" },
		{ key: "webmaster", label: "ВебМастер" },
	];

	const strategyLabels: Record<string, string> = { daily: "Ежедневная", monthly: "Ежемесячная", hourly: "Почасовая" };

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

				<!-- Activity toggle -->
				<div class="flex flex-col gap-2">
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
					<button onclick={deleteProject} class="px-4 py-2 rounded-lg text-sm font-medium bg-red-50 hover:bg-red-100 text-red-600 transition-colors">Удалить проект</button>
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
						<button onclick={() => { proklikMode = "all"; showProklik = true; }} class="px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors font-medium">Проклик</button>
						{#if selectedQueryIds.size > 0}
							<button onclick={() => { proklikMode = "selected"; proklikQueries = [...selectedQueryIds]; showProklik = true; }} class="px-3 py-1.5 text-sm bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors">Проклик (выбранные: {selectedQueryIds.size})</button>
							<button onclick={selectAll} class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Снять все</button>
						{:else}
							<button onclick={selectAll} class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Выбрать все</button>
						{/if}
					</div>
				</div>

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
							{#each queries as query}
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
											<button onclick={() => startEdit(query)} class="text-sm font-medium text-gray-900 hover:text-blue-600 cursor-pointer">{query.daily_clicks}</button>
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
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">
				<a href="/analytics" class="text-blue-600 hover:text-blue-700">Перейти к аналитике →</a>
			</div>

		{:else if activeTab === 'positions'}
			<!-- Positions tab -->
			<div class="mb-4">
				<p class="text-sm text-gray-500">История позиций по запросам. Данные обновляются каждые 10 секунд.</p>
			</div>

			{#if positionsData.length === 0}
				<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">Нет данных о позициях. Позиции появятся после завершения первых задач.</div>
			{:else}
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
