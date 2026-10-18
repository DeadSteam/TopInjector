<script lang="ts">
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	interface QueueTask {
		id: string;
		query: string;
		click_url: string;
		source: 'strategy' | 'autoburst' | 'proklik';
		status: 'pending' | 'in_progress' | 'completed' | 'not_found' | 'stuck';
		geo: any;
		created_at: string;
		position?: number;
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
			projects = await api.projects.list();
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
			let statusFilter = filterStatus === "all" ? undefined : filterStatus;
			const data = await api.queue.list(projectId || undefined, statusFilter, filterFromDate || undefined, filterToDate || undefined, filterIntegration || undefined);
			tasks = data.tasks || [];
			updateStats();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	function clearDateFilters() {
		filterFromDate = "";
		filterToDate = "";
		loadQueue();
	}

	function updateStats() {
		stats = {
			pending: tasks.filter(t => t.status === 'pending').length,
			in_progress: tasks.filter(t => t.status === 'in_progress').length,
			completed: tasks.filter(t => t.status === 'completed').length,
			not_found: tasks.filter(t => t.status === 'not_found').length,
			stuck: tasks.filter(t => t.status === 'stuck').length,
		};
		lastUpdate = new Date().toLocaleTimeString('ru-RU');
	}

	function startSSE() {
		stopSSE();
		const es = api.queue.feed(projectId || undefined, filterFromDate || undefined, filterToDate || undefined, filterIntegration || undefined);
		eventSource = es;

		eventSource.onopen = () => {
			isConnected = true;
			console.log("SSE connected");
		};

		eventSource.addEventListener('stats', (e: any) => {
			try {
				const data = JSON.parse(e.data);
				if (data.type === 'stats') {
					stats = data.data;
					lastUpdate = new Date().toLocaleTimeString('ru-RU');
				}
			} catch {
				// ignore parse errors
			}
		});

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
		if (!confirm("Очистить все ожидающие задачи?")) return;
		try {
			await api.queue.clear("");
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
		refreshInterval = window.setInterval(() => {
			// Only refresh tasks on interval, SSE reconnects via $effect
			if (filterStatus === "all" || filterSource === "all") {
				loadQueue();
			}
		}, 15000); // Poll every 15s as fallback
	});

	onDestroy(() => {
		stopSSE();
		if (refreshInterval) clearInterval(refreshInterval);
	});

	// Reconnect SSE + reload queue when project or date filters change
	$effect(() => {
		const _ = projectId;
		const __ = filterFromDate;
		const ___ = filterToDate;
		startSSE();
		loadQueue();
		return () => {};
	});

	function refresh() { loadQueue(); }

	const filteredTasks = $derived(
		filterStatus === "all" ? tasks : tasks.filter(t => t.status === filterStatus)
	);
</script>

<div class="p-6">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900">Очередь задач</h1>
			<p class="text-sm text-gray-500 mt-1">Мониторинг выполнения в реальном времени</p>
		</div>
		<div class="flex items-center gap-3">
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
		<div class="grid grid-cols-5 gap-4 mb-6">
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
					<select bind:value={projectId} onchange={() => loadQueue()}
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
		<div class="mb-4 flex gap-2">
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
		</div>

		<!-- Source filter -->
		<div class="mb-4 flex gap-2">
			<button onclick={() => { filterSource = 'all'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'all' ? 'bg-gray-800 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Все источники
			</button>
			<button onclick={() => { filterSource = 'strategy'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'strategy' ? 'bg-purple-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Стратегия
			</button>
			<button onclick={() => { filterSource = 'autoburst'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'autoburst' ? 'bg-orange-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Автобёрст
			</button>
			<button onclick={() => { filterSource = 'proklik'; loadQueue(); }}
				class="px-3 py-1.5 text-sm rounded-lg transition-colors {filterSource === 'proklik' ? 'bg-pink-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}">
				Проклик
			</button>
		</div>

		<!-- Integration filter -->
		{#if integrations.length > 0}
		<div class="mb-4 flex gap-2 flex-wrap">
			<span class="text-sm text-gray-500 py-1.5">Интеграция:</span>
			<button onclick={() => { filterIntegration = ''; loadQueue(); }}
				class='px-3 py-1.5 text-sm rounded-lg transition-colors {filterIntegration === "" ? "bg-blue-600 text-white" : "border border-gray-300 hover:bg-gray-50"}'>
				Все
			</button>
			{#each integrations as integ}
				<button onclick={() => { filterIntegration = integ.key; loadQueue(); }}
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
								<td class="px-4 py-3 text-blue-600 truncate max-w-[200px]"><a href={task.click_url} target="_blank" class="hover:underline">{task.click_url}</a></td>
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
			{/if}
		</div>
	{/if}
</div>
<!-- Task detail modal -->
{#if showTaskDetail && taskDetail}
<div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50" onclick={(e) => { if (e.target === e.currentTarget) { showTaskDetail = false; taskDetail = null; } }}>
<div class="bg-white rounded-xl shadow-2xl max-w-lg w-full">
<div class="flex items-center justify-between p-4 border-b border-gray-200">
<h3 class="text-lg font-semibold text-gray-900">Task Detail</h3>
<button onclick={() => { showTaskDetail = false; taskDetail = null; }} class="text-gray-400 hover:text-gray-600">&times;</button>
</div>
<div class="p-4 space-y-3">
<div><p class="text-xs text-gray-500 mb-1">URL</p><p class="text-sm text-gray-900 break-all">{taskDetail.click_url}</p></div>
<div class="grid grid-cols-2 gap-3">
<div><p class="text-xs text-gray-500">Source</p><span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-100 text-purple-700">{sourceLabels[taskDetail.source] || taskDetail.source}</span></div>
<div><p class="text-xs text-gray-500">Status</p><span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium {statusColors[taskDetail.status]}">{statusLabels[taskDetail.status]}</span></div>
</div>
{#if taskDetail.position}<div><p class="text-xs text-gray-500">Position</p><p class="text-sm text-gray-900">#{taskDetail.position}</p></div>{/if}
<div><p class="text-xs text-gray-500">Created</p><p class="text-sm text-gray-900">{new Date(taskDetail.created_at).toLocaleString("ru-RU")}</p></div>
</div>
<div class="p-4 border-t border-gray-200 flex justify-end"><button onclick={() => { showTaskDetail = false; taskDetail = null; }} class="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors">Close</button></div>
</div></div>{/if}