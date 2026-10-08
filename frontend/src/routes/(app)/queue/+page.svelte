<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	interface QueueTask {
		id: string;
		query: string;
		click_url: string;
		source: 'strategy' | 'autoburst' | 'proklik';
		status: 'pending' | 'in_progress' | 'completed' | 'not_found' | 'stuck';
		geo: any;
		created_at: string;
	}

	let tasks = $state<QueueTask[]>([]);
	let filterStatus = $state<string>("all");
	let loading = $state(true);
	let error = $state("");
	let stats = $state({ pending: 0, in_progress: 0, completed: 0, not_found: 0, stuck: 0 });

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
			const data = await api.queue.list(undefined, statusFilter);
			tasks = data.tasks || [];
			stats = {
				pending: tasks.filter(t => t.status === 'pending').length,
				in_progress: tasks.filter(t => t.status === 'in_progress').length,
				completed: tasks.filter(t => t.status === 'completed').length,
				not_found: tasks.filter(t => t.status === 'not_found').length,
				stuck: tasks.filter(t => t.status === 'stuck').length,
			};
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	onMount(() => { loadQueue(); });

	function refresh() { loadQueue(); }
</script>

<div class="p-6">
	<div class="flex items-center justify-between mb-6">
		<div>
			<h1 class="text-2xl font-bold text-gray-900">Очередь задач</h1>
			<p class="text-sm text-gray-500 mt-1">Мониторинг выполнения задач в реальном времени</p>
		</div>
		<button onclick={refresh} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
			Обновить
		</button>
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
		</div>

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
							<th class="px-4 py-3 text-left font-medium text-gray-600">Гео</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Создана</th>
						</tr>
					</thead>
					<tbody>
						{#each tasks as task}
							<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
								<td class="px-4 py-3 font-mono text-xs">{task.id.slice(0, 8)}</td>
								<td class="px-4 py-3 text-blue-600 truncate max-w-[200px]"><a href={task.click_url} target="_blank" class="hover:underline">{task.click_url}</a></td>
								<td class="px-4 py-3"><span class="text-xs bg-gray-100 px-2 py-1 rounded">{sourceLabels[task.source] || task.source}</span></td>
								<td class="px-4 py-3"><span class="inline-flex px-2 py-1 rounded-full text-xs font-medium {statusColors[task.status]}">{statusLabels[task.status]}</span></td>
								<td class="px-4 py-3 text-gray-600">{task.geo ? JSON.stringify(task.geo) : '—'}</td>
								<td class="px-4 py-3 text-gray-500 text-xs">{new Date(task.created_at).toLocaleString('ru-RU')}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if tasks.length === 0}
				<div class="px-4 py-12 text-center text-gray-400">Нет задач в очереди</div>
			{/if}
		</div>
	{/if}
</div>
