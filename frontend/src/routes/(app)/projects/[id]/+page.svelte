<script lang="ts">
	import { page } from '$app/stores';
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	interface QueryRow {
		id: string;
		text: string;
		url: string;
		click_url: string;
		geo: any;
		daily_clicks: number;
		position: number | null;
		completed: number;
	}

	let projectId = $state("");
	let project = $state<any>(null);
	let queries = $state<QueryRow[]>([]);
	let activeTab = $state("queries");
	let loading = $state(true);
	let error = $state("");
	let newQueryText = $state("");

	async function loadProject() {
		try {
			project = await api.projects.get(projectId);
			queries = await api.projects.queries(projectId);
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	async function addQuery() {
		if (!newQueryText.trim()) return;
		try {
			await api.projects.addQuery(projectId, { text: newQueryText });
			newQueryText = "";
			await loadProject();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка добавления";
		}
	}

	onMount(() => {
		// Extract project ID from URL params (SvelteKit 2)
		projectId = window.location.pathname.split('/projects/')[1] || "";
		loadProject();
	});

	const tabList = [
		{ key: "queries", label: "Запросы" },
		{ key: "queue", label: "Очередь" },
		{ key: "analytics", label: "Аналитика" },
		{ key: "positions", label: "Позиции" },
		{ key: "markers", label: "Маркеры" },
		{ key: "webmaster", label: "ВебМастер" },
	];

	function getTabLabel(tab: string): string {
		return tabList.find(t => t.key === tab)?.label || tab;
	}
</script>

<div class="p-6">
	<!-- Project header -->
	<div class="mb-6">
		<a href="/" class="text-sm text-blue-600 hover:text-blue-700 mb-2 inline-block">← Все проекты</a>
		{#if project}
			<h1 class="text-xl font-bold text-gray-900">{project.name}</h1>
			<p class="text-sm text-gray-500 mt-1">{project.domain} · {project.region || '—'} · {project.strategy_type} стратегия</p>
		{/if}
	</div>

	<!-- Tabs -->
	<div class="border-b border-gray-200 mb-6">
		<nav class="-mb-px flex space-x-6">
			{#each tabList as tab}
				<button
					class={`py-3 px-1 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
					onclick={() => (activeTab = tab.key)}
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
		<!-- Queries tab content -->
		{#if activeTab === 'queries'}
			<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
				<!-- Table toolbar -->
				<div class="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
					<form onsubmit={(e) => { e.preventDefault(); addQuery(); }} class="flex items-center gap-2">
						<input type="text" bind:value={newQueryText} placeholder="Добавить запрос..." class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none w-64" />
						<button type="submit" class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">Добавить</button>
					</form>
					<div class="flex items-center gap-2">
						<button class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Импорт запросов</button>
						<button class="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Экспорт</button>
					</div>
				</div>

				<!-- Queries table -->
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="bg-gray-50 border-b border-gray-200">
							<tr>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Запрос</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">URL</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Click URL</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Гео</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Кликов/день</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Позиция</th>
								<th class="px-4 py-3 text-left font-medium text-gray-600">Сделано</th>
							</tr>
						</thead>
						<tbody>
							{#each queries as query}
								<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
									<td class="px-4 py-3 font-medium text-gray-900">{query.text}</td>
									<td class="px-4 py-3 text-blue-600 truncate max-w-[200px]"><a href={query.url} target="_blank" class="hover:underline">{query.url || '—'}</a></td>
									<td class="px-4 py-3 text-gray-500">{query.click_url || '—'}</td>
									<td class="px-4 py-3 text-gray-600">{query.geo ? JSON.stringify(query.geo) : '—'}</td>
									<td class="px-4 py-3 text-gray-600">{query.daily_clicks}</td>
									<td class="px-4 py-3 text-gray-500">{query.position ?? 'N/A'}</td>
									<td class="px-4 py-3">
										<span class="font-medium text-green-600">{query.completed.toLocaleString()}</span>
									</td>
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
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">
				<a href="/queue" class="text-blue-600 hover:text-blue-700">Перейти к очереди задач →</a>
			</div>
		{:else if activeTab === 'analytics'}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">
				<a href="/analytics" class="text-blue-600 hover:text-blue-700">Перейти к аналитике →</a>
			</div>
		{:else}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm text-center text-gray-400">
				{getTabLabel(activeTab)} — в разработке
			</div>
		{/if}
	{/if}
</div>
