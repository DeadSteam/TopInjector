<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	let warmups = $state<any[]>([]);
	let projects = $state<any[]>([]);
	let loading = $state(true);
	let showCreateModal = $state(false);
	let error = $state("");

	// Create form
	let newName = $state("");
	let newProjectId = $state("");
	let newClicksPerHour = $state(10);
	let newTotalTarget = $state(100);
	let newStartTime = $state("");
	let newEndTime = $state("");

	async function loadWarmups() {
		try { warmups = await api.warmups.list(); } catch (e) { error = e instanceof Error ? e.message : "Ошибка"; }
	}

	async function loadProjects() {
		try {
			projects = await api.projects.all();
		} catch {}
	}

	async function createWarmup() {
		if (!newName.trim()) return;
		try {
			await api.warmups.create({
				name: newName,
				project_id: newProjectId || undefined,
				clicks_per_hour: Number(newClicksPerHour) || 10,
				total_target: Number(newTotalTarget) || 100,
				start_time: newStartTime || undefined,
				end_time: newEndTime || undefined,
			});
			showCreateModal = false;
			newName = ""; newProjectId = ""; newClicksPerHour = 10; newTotalTarget = 100;
			newStartTime = ""; newEndTime = "";
			await loadWarmups();
		} catch (e) { error = e instanceof Error ? e.message : "Ошибка создания"; }
	}

	async function updateStatus(id: string, status: string) {
		try { await api.warmups.update(id, { status }); await loadWarmups(); } catch {}
	}

	async function deleteWarmup(id: string) {
		if (!confirm("Удалить кампанию?")) return;
		await api.warmups.delete(id);
		await loadWarmups();
	}

	async function tickWarmup(id: string) {
		try {
			const res = await api.warmups.tick(id);
			if (res.status === "completed") await loadWarmups();
		} catch {}
	}

	onMount(() => { loadWarmups(); loadProjects(); });
</script>

<div class="p-6">
	<div class="flex flex-wrap items-center justify-between gap-3 mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Разогрев (Warmups)</h1>
		<button onclick={() => showCreateModal = true} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">+ Создать кампанию</button>
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	{#if warmups.length === 0}
		<div class="text-center py-16 bg-white rounded-xl border border-gray-200">
			<svg class="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/></svg>
			<p class="text-gray-500 mb-2">Нет кампаний разогрева</p>
			<p class="text-sm text-gray-400">Создайте кампанию для предварительной имитации поискового трафика</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each warmups as warmup}
				<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
					<div class="flex items-center justify-between mb-3">
						<h3 class="font-semibold text-gray-900">{warmup.name}</h3>
						<span class="px-2 py-1 rounded-full text-xs font-medium
							{warmup.status === 'active' ? 'bg-green-100 text-green-800' :
							 warmup.status === 'draft' ? 'bg-gray-100 text-gray-600' :
							 warmup.status === 'completed' ? 'bg-blue-100 text-blue-800' :
							 warmup.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
							 'bg-red-100 text-red-800'}">
							{warmup.status === 'active' ? 'Активна' :
							 warmup.status === 'draft' ? 'Черновик' :
							 warmup.status === 'completed' ? 'Завершена' :
							 warmup.status === 'paused' ? 'На паузе' :
							 warmup.status}
						</span>
					</div>

					{#if warmup.project_name}
						<p class="text-xs text-gray-500 mb-2">Проект: {warmup.project_name}</p>
					{/if}

					<div class="space-y-2 mb-4">
						<div class="flex justify-between text-sm">
							<span class="text-gray-500">Кликов/час</span>
							<span class="font-medium">{warmup.clicks_per_hour}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-500">Цель</span>
							<span class="font-medium">{warmup.total_target}</span>
						</div>
						<div class="flex justify-between text-sm">
							<span class="text-gray-500">Выполнено</span>
							<span class="font-bold text-green-600">{warmup.completed_clicks}</span>
						</div>
					</div>

					<!-- Progress bar -->
					<div class="mb-4">
						<div class="w-full bg-gray-200 rounded-full h-2">
							<div class="bg-blue-600 h-2 rounded-full transition-all" style="width: {Math.min((warmup.completed_clicks / (warmup.total_target || 1)) * 100, 100)}%"></div>
						</div>
						<p class="text-xs text-gray-400 mt-1">{Math.round((warmup.completed_clicks / (warmup.total_target || 1)) * 100)}%</p>
					</div>

					<div class="flex gap-2">
						{#if warmup.status === 'draft'}
							<button onclick={() => updateStatus(warmup.id, 'active')} class="flex-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs rounded-lg transition-colors">Запустить</button>
						{:else if warmup.status === 'active'}
							<button onclick={() => tickWarmup(warmup.id)} class="flex-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg transition-colors">+ Клик</button>
							<button onclick={() => updateStatus(warmup.id, 'paused')} class="px-3 py-1.5 border border-gray-300 text-gray-600 text-xs rounded-lg hover:bg-gray-50">Пауза</button>
						{:else if warmup.status === 'paused'}
							<button onclick={() => updateStatus(warmup.id, 'active')} class="flex-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs rounded-lg transition-colors">Продолжить</button>
						{/if}
						<button onclick={() => deleteWarmup(warmup.id)} class="px-3 py-1.5 border border-red-300 text-red-600 text-xs rounded-lg hover:bg-red-50">Удалить</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Create Modal -->
	{#if showCreateModal}
		<div class="fixed inset-0 bg-black/40 flex items-start justify-center z-50 pt-24 px-4" onclick={(e) => { if (e.target === e.currentTarget) showCreateModal = false; }}>
			<div class="bg-white rounded-xl shadow-2xl w-full max-w-md overflow-hidden">
				<div class="flex items-center justify-between px-4 py-3 border-b border-gray-200">
					<h3 class="text-base font-semibold text-gray-900">Новая кампания разогрева</h3>
					<button onclick={() => showCreateModal = false} class="text-gray-400 hover:text-gray-600">&times;</button>
				</div>
				<div class="p-4 space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Название</label>
						<input type="text" bind:value={newName} placeholder="Утренняя кампания" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Проект (необязательно)</label>
						<select bind:value={newProjectId} class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
							<option value="">Все проекты</option>
							{#each projects as p}
								<option value={p.id}>{p.name}</option>
							{/each}
						</select>
					</div>
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Кликов/час</label>
							<input type="number" bind:value={newClicksPerHour} min="1" max="1000" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Цель (клики)</label>
							<input type="number" bind:value={newTotalTarget} min="10" max="100000" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
					</div>
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Начало</label>
							<input type="datetime-local" bind:value={newStartTime} class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 mb-1">Окончание</label>
							<input type="datetime-local" bind:value={newEndTime} class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
					</div>
				</div>
				<div class="flex gap-2 px-4 py-3 bg-gray-50 border-t border-gray-200">
					<button onclick={() => showCreateModal = false} class="flex-1 px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-100 transition-colors">Отмена</button>
					<button onclick={createWarmup} class="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">Создать</button>
				</div>
			</div>
		</div>
	{/if}
</div>
