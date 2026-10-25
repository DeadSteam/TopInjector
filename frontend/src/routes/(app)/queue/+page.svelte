<script lang="ts">
	import { api, safeHref } from "$lib/api";
	import { onMount, onDestroy, untrack } from 'svelte';

	interface QueueTask {
		id: string;
		project_id: string;
		project_name: string;
		click_url: string;
		source: 'strategy' | 'autoburst' | 'proklik';
		status: 'pending' | 'in_progress' | 'completed' | 'not_found' | 'stuck';
		geo: any;
		position: number | null;
		details: string | null;
		created_at: string;
		updated_at: string | null;
	}

	const LIST_LIMIT = 500;  // newest tasks shown; the counters above cover everything

	// Search URLs are percent-encoded; show the query text readably
	function prettyUrl(url: string): string {
		try { return decodeURI(url); } catch { return url; }
	}

	let tasks = $state<QueueTask[]>([]);
	let filterStatus = $state<string>("all");
	let filterSource = $state<string>("all");
	let filterIntegration = $state<string>("");
	let loading = $state(true);
	let error = $state("");
	let stats = $state({ pending: 0, in_progress: 0, completed: 0, not_found: 0, stuck: 0 });
	let isConnected = $state(false);
	let lastUpdate = $state<string>("");
	let projectId = $state("");
	let showTaskDetail = $state(false);
	let taskDetail = $state<QueueTask | null>(null);

	// Filters: project list + date range
	let integrations = $state<any[]>([]);
	let projects = $state<any[]>([]);
	let filterFromDate = $state("");
	let filterToDate = $state("");

	function openTaskDetail(id: string): void {
		const task = tasks.find(t => t.id === id);
		if (task) {
			taskDetail = task;
			showTaskDetail = true;
		}
	}

	async function loadProjects() {
		try {
			projects = await api.projects.all();
		} catch { /* ignore */ }
	}

	async function loadIntegrations() {
		try {
			const res = await api.projects.integrations();
			integrations = res.integrations || [];
		} catch { /* ignore */ }
	}

	let eventSource: EventSource | null = null;

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

	const sourceLabels: Record<string, string> = {
		strategy: 'Стратегия',
		autoburst: 'Автобёрст',
		proklik: 'Проклик',
	};

	async function loadQueue() {
		try {
			const statusFilter = filterStatus === "all" ? undefined : filterStatus;
			const [list, counts] = await Promise.all([
				api.queue.list(projectId || undefined, statusFilter, filterFromDate || undefined, filterToDate || undefined, filterIntegration || undefined, LIST_LIMIT),
				api.queue.stats(projectId || undefined, filterIntegration || undefined, filterFromDate || undefined, filterToDate || undefined),
			]);
			tasks = list;
			stats = counts;
			lastUpdate = new Date().toLocaleTimeString('ru-RU');
			error = "";
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	function clearDateFilters() {
		filterFromDate = "";
		filterToDate = "";
	}

	function startSSE() {
		stopSSE();
		const es = api.queue.feed(projectId || undefined, filterFromDate || undefined, filterToDate || undefined, filterIntegration || undefined);
		eventSource = es;

		eventSource.onopen = () => {
			isConnected = true;
			console.log("SSE connected");
		};

		// The feed sends unnamed events ("data: {...}"), which arrive as "message"
		eventSource.onmessage = (e: MessageEvent) => {
			try {
				const data = JSON.parse(e.data);
				if (data.type === 'stats') {
					stats = data.data;
					lastUpdate = new Date().toLocaleTimeString('ru-RU');
				}
			} catch {
				// ignore parse errors
			}
		};

		eventSource.onerror = () => {
			isConnected = false;
			eventSource?.close();
			eventSource = null;
		};
	}

	function stopSSE() {
		if (eventSource) {
			eventSource.close();
			eventSource = null;
		}
		isConnected = false;
	}

	async function clearPending() {
		if (!projectId) {
			error = "Выберите проект, очередь которого нужно очистить";
			return;
		}
		if (!confirm("Очистить все ожидающие задачи проекта?")) return;
		try {
			await api.queue.clear(projectId);
			await loadQueue();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка очистки";
		}
	}

	let refreshInterval: number | null = null;

	onMount(() => {
		loadProjects();
		loadIntegrations();
		// loadQueue and startSSE are handled by $effect below
		refreshInterval = window.setInterval(loadQueue, 15000); // the list itself isn't streamed
	});

	onDestroy(() => {
		stopSSE();
		if (refreshInterval) clearInterval(refreshInterval);
	});

	// Reconnect SSE + reload queue when project, date or integration filters change
	$effect(() => {
		projectId;
		filterFromDate;
		filterToDate;
		filterIntegration;
		untrack(() => {  // depend only on the filters above, not on what the loaders read
			startSSE();
			loadQueue();
		});
	});

	function refresh() { loadQueue(); }

	const filteredTasks = $derived(
		tasks.filter(t =>
			(filterStatus === "all" || t.status === filterStatus) &&
			(filterSource === "all" || t.source === filterSource)
		)
	);
</script>

<div class="p-6">
	<div class="flex flex-wrap items-center justify-between gap-3 mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900">Очередь задач</h1>
			<p class="text-sm text-gray-500 mt-1">Мониторинг выполнения в реальном времени</p>
		</div>
		<div class="flex flex-wrap items-center gap-3">
			<div class="flex items-center gap-2">
				<span class="w-2 h-2 rounded-full {isConnected ? 'bg-green-500' : 'bg-red-500'}"></span>
				<span class="text-xs text-gray-500">{isConnected ? 'Онлайн' : 'Оффлайн'}</span>
			</div>
			{#if lastUpdate}
				<span class="text-xs text-gray-400">Обновлено: {lastUpdate}</span>
			{/if}
			<button onclick={refresh} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
				Обновить
			</button>
			<button onclick={clearPending} class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors">
				Очистить pending
			</button>
		</div>
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}
		<!-- Queue stats -->
		<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4 mb-6">
			{#each ['pending', 'in_progress', 'completed', 'not_found', 'stuck'] as status}
				<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm text-center">
					<span class="inline-flex px-2 py-1 rounded-full text-xs font-medium {statusColors[status]}">{statusLabels[status]}</span>
					<p class="text-2xl font-bold text-gray-900 mt-2">{stats[status as keyof typeof stats]}</p>
				</div>
			{/each}
		</div>

		<!-- Project + date range filters -->
		<div class="bg-white border border-gray-200 rounded-xl p-4 mb-4">
			<div class="flex flex-wrap items-end gap-3">
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Проект</label>
					<select bind:value={projectId}
						class="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 min-w-[180px]">
						<option value="">Все проекты</option>
						{#each projects as p}
							<option value={p.id}>{p.name}</option>
						{/each}
					</select>
				</div>
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Период с</label>
					<input type="date" bind:value={filterFromDate}
						class="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
				</div>
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Период по</label>
					<input type="date" bind:value={filterToDate}
						class="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
				</div>
				{#if filterFromDate || filterToDate}
					<button onclick={clearDateFilters} class="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors">Очистить</button>
				{/if}
			</div>
		</div>

		<!-- Filter -->
		<div class="mb-4 flex flex-wrap gap-2">
			<button onclick={() => { filterStatus = 'all'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterStatus === 'all' ? 'bg-blue-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Все
			</button>
			<button onclick={() => { filterStatus = 'pending'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterStatus === 'pending' ? 'bg-yellow-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Ожидает
			</button>
			<button onclick={() => { filterStatus = 'in_progress'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterStatus === 'in_progress' ? 'bg-blue-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Выполняется
			</button>
			<button onclick={() => { filterStatus = 'completed'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterStatus === 'completed' ? 'bg-green-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Завершённые
			</button>
			<button onclick={() => { filterStatus = 'not_found'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterStatus === 'not_found' ? 'bg-red-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Не найден
			</button>
			<button onclick={() => { filterStatus = 'stuck'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterStatus === 'stuck' ? 'bg-orange-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Завис
			</button>
		</div>

		<!-- Source filter -->
		<div class="mb-4 flex flex-wrap gap-2">
			<button onclick={() => { filterSource = 'all'; }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'all' ? 'bg-gray-800 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Все источники
			</button>
			<button onclick={() => { filterSource = 'strategy'; }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'strategy' ? 'bg-purple-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Стратегия
			</button>
			<button onclick={() => { filterSource = 'autoburst'; }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'autoburst' ? 'bg-orange-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Автобёрст
			</button>
			<button onclick={() => { filterSource = 'proklik'; }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'proklik' ? 'bg-pink-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Проклик
			</button>
		</div>

		<!-- Integration filter -->
		{#if integrations.length > 0}
		<div class="mb-4 flex gap-2 flex-wrap">
			<span class="text-sm text-gray-500 py-1.5">Интеграция:</span>
			<button onclick={() => { filterIntegration = ''; }}
				class='px-3 py-1.5 text-sm rounded-lg transition-colors {filterIntegration === "" ? "bg-blue-600 text-white" : "border border-gray-300 hover:bg-gray-50"}'>
				Все
			</button>
			{#each integrations as integ}
				<button onclick={() => { filterIntegration = integ.key; }}
					class='px-3 py-1.5 text-sm rounded-lg transition-colors {filterIntegration === integ.key ? "bg-blue-600 text-white" : "border border-gray-300 hover:bg-gray-50"}' title={integ.description || integ.key}>
					{integ.label || integ.key}
				</button>
			{/each}
		</div>
		{/if}

		<!-- Task list -->
		<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 border-b border-gray-200">
						<tr>
							<th class="px-4 py-3 text-left font-medium text-gray-600">ID</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Проект</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">URL</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Источник</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Статус</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Позиция</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Создана</th>
						</tr>
					</thead>
					<tbody>
						{#each filteredTasks as task}
							<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer" onclick={() => openTaskDetail(task.id)}>
								<td class="px-4 py-3 font-mono text-xs">{task.id.slice(0, 8)}</td>
								<td class="px-4 py-3 text-gray-700 truncate max-w-[160px]">{task.project_name}</td>
								<td class="px-4 py-3 text-blue-600 truncate max-w-[200px]"><a href={safeHref(task.click_url)} target="_blank" rel="noopener noreferrer" class="hover:underline" onclick={(e) => e.stopPropagation()}>{prettyUrl(task.click_url)}</a></td>
								<td class="px-4 py-3"><span class="text-xs bg-gray-100 px-2 py-1 rounded">{sourceLabels[task.source] || task.source}</span></td>
								<td class="px-4 py-3"><span class="inline-flex px-2 py-1 rounded-full text-xs font-medium {statusColors[task.status]}">{statusLabels[task.status]}</span></td>
								<td class="px-4 py-3">
									{#if task.position}
										<span class={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
											task.position <= 3 ? 'bg-green-100 text-green-800' :
											task.position <= 10 ? 'bg-blue-100 text-blue-800' :
											'bg-gray-100 text-gray-800'
										}`}>
											#{task.position}
										</span>
									{:else}
										<span class="text-gray-400">—</span>
									{/if}
								</td>
								<td class="px-4 py-3 text-gray-500 text-xs">{new Date(task.created_at).toLocaleString('ru-RU')}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if filteredTasks.length === 0}
				<div class="px-4 py-12 text-center text-gray-400">
					{filterStatus === 'all' ? 'Нет задач в очереди' : `Нет задач со статусом "${statusLabels[filterStatus]}"`}
				</div>
			{:else if tasks.length >= LIST_LIMIT}
				<div class="px-4 py-3 text-center text-xs text-gray-400 border-t border-gray-100">
					Показаны последние {LIST_LIMIT} задач. Сузьте период или выберите проект, чтобы увидеть более ранние
				</div>
			{/if}
		</div>
	{/if}
</div>
<!-- Task detail modal -->
{#if showTaskDetail && taskDetail}
<div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50" onclick={(e) => { if (e.target === e.currentTarget) { showTaskDetail = false; taskDetail = null; } }}>
<div class="bg-white rounded-xl shadow-2xl max-w-lg w-full">
<div class="flex items-center justify-between p-4 border-b border-gray-200">
<h3 class="text-lg font-semibold text-gray-900">Задача <span class="font-mono text-sm text-gray-500">{taskDetail.id.slice(0, 8)}</span></h3>
<button onclick={() => { showTaskDetail = false; taskDetail = null; }} class="text-gray-400 hover:text-gray-600" aria-label="Закрыть">&times;</button>
</div>
<div class="p-4 space-y-3">
<div><p class="text-xs text-gray-500 mb-1">Проект</p><a href="/projects/{taskDetail.project_id}" class="text-sm text-blue-600 hover:underline">{taskDetail.project_name}</a></div>
<div><p class="text-xs text-gray-500 mb-1">URL</p><a href={safeHref(taskDetail.click_url)} target="_blank" rel="noopener noreferrer" class="text-sm text-blue-600 hover:underline break-all">{prettyUrl(taskDetail.click_url)}</a></div>
<div class="grid grid-cols-2 gap-3">
<div><p class="text-xs text-gray-500">Источник</p><span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-100 text-purple-700">{sourceLabels[taskDetail.source] || taskDetail.source}</span></div>
<div><p class="text-xs text-gray-500">Статус</p><span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium {statusColors[taskDetail.status]}">{statusLabels[taskDetail.status]}</span></div>
<div><p class="text-xs text-gray-500">Позиция</p><p class="text-sm text-gray-900">{taskDetail.position ? `#${taskDetail.position}` : '—'}</p></div>
<div><p class="text-xs text-gray-500">Гео</p><p class="text-sm text-gray-900">{taskDetail.geo?.region || taskDetail.geo?.city || '—'}</p></div>
<div><p class="text-xs text-gray-500">Создана</p><p class="text-sm text-gray-900">{new Date(taskDetail.created_at).toLocaleString("ru-RU")}</p></div>
<div><p class="text-xs text-gray-500">Последнее изменение</p><p class="text-sm text-gray-900">{taskDetail.updated_at ? new Date(taskDetail.updated_at).toLocaleString("ru-RU") : '—'}</p></div>
</div>
{#if taskDetail.details}<div><p class="text-xs text-gray-500 mb-1">Комментарий агента</p><p class="text-sm text-gray-900 whitespace-pre-wrap break-words">{taskDetail.details}</p></div>{/if}
</div>
<div class="p-4 border-t border-gray-200 flex justify-end"><button onclick={() => { showTaskDetail = false; taskDetail = null; }} class="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors">Закрыть</button></div>
</div></div>{/if}
