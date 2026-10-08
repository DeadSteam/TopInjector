<script lang="ts">
	import "../app.css";
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	interface Project {
		id: string;
		name: string;
		domain: string;
		region: string;
		strategy_type: string;
		daily_limit: number;
		is_active: boolean;
		queryCount: number;
		clicksDone: number;
		queuePending: number;
	}

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let showCreateModal = $state(false);
	let error = $state("");

	// New project form
	let newName = $state("");
	let newDomain = $state("");
	let newRegion = $state("");
	let newStrategy = $state("daily");

	async function loadProjects() {
		try {
			projects = await api.projects.list();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	async function createProject() {
		if (!newName || !newDomain) return;
		try {
			await api.projects.create({
				name: newName,
				domain: newDomain,
				region: newRegion || null,
				strategy_type: newStrategy,
				daily_limit: 100,
			});
			showCreateModal = false;
			newName = ""; newDomain = ""; newRegion = "";
			await loadProjects();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка создания";
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

	onMount(() => { loadProjects(); });
</script>

<div class="p-6">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Проекты</h1>
		<button
			class="py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
			onclick={() => (showCreateModal = true)}
		>
			+ Создать проект
		</button>
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
			{error}
		</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}
		<!-- Projects table -->
		<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 border-b border-gray-200">
						<tr>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Название</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Домен</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Регион</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Стратегия</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Лимит/день</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Действия</th>
						</tr>
					</thead>
					<tbody>
						{#each projects as project}
							<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
								<td class="px-4 py-3">
									<a href="/projects/{project.id}" class="font-medium text-blue-600 hover:text-blue-700">
										{project.name}
									</a>
								</td>
								<td class="px-4 py-3 text-gray-600">{project.domain}</td>
								<td class="px-4 py-3 text-gray-600">{project.region || '—'}</td>
								<td class="px-4 py-3">
									<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium
										{project.strategy_type === 'daily' ? 'bg-blue-100 text-blue-800' : project.strategy_type === 'monthly' ? 'bg-purple-100 text-purple-800' : 'bg-green-100 text-green-800'}">
										{project.strategy_type}
									</span>
								</td>
								<td class="px-4 py-3 text-gray-600">{project.daily_limit}</td>
								<td class="px-4 py-3">
									<button onclick={() => deleteProject(project.id)} class="text-red-500 hover:text-red-700 text-xs">Удалить</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			{#if projects.length === 0}
				<div class="px-4 py-12 text-center text-gray-400">
					Нет проектов. Создайте первый проект для начала работы.
				</div>
			{/if}
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
						<input type="text" bind:value={newName} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="Мой проект" required />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Домен</label>
						<input type="url" bind:value={newDomain} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="https://example.com" required />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Регион</label>
						<input type="text" bind:value={newRegion} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="Москва" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Стратегия распределения</label>
						<select bind:value={newStrategy} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
							<option value="daily">Суточная (равномерно по дням)</option>
							<option value="monthly">Месячная</option>
							<option value="hourly">Часовая (равномерно по часам)</option>
						</select>
					</div>
				</form>

				<div class="flex justify-end gap-3 mt-6">
					<button onmousedown={(e) => { e.stopPropagation(); showCreateModal = false; }} class="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors">
						Отмена
					</button>
					<button type="submit" form="createForm" onclick={createProject} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
						Создать проект
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
