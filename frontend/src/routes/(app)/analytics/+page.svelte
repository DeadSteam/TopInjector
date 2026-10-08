<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	interface Stats {
		total_clicks: number;
		completed_rate: number;
		avg_position: number;
		projects_active: number;
	}

	let stats = $state<Stats | null>(null);
	let loading = $state(true);
	let error = $state("");

	async function loadAnalytics() {
		try {
			stats = await api.analytics.summary();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	onMount(() => { loadAnalytics(); });
</script>

<div class="p-6">
	<div class="mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Аналитика</h1>
		<p class="text-sm text-gray-500 mt-1">Статистика кликов, позиций и эффективности проектов</p>
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else if stats}
		<!-- Stats cards -->
		<div class="grid grid-cols-4 gap-6 mb-8">
			<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
				<p class="text-sm text-gray-500">Всего кликов</p>
				<p class="text-3xl font-bold text-gray-900 mt-1">{stats.total_clicks.toLocaleString()}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
				<p class="text-sm text-gray-500">Успешность</p>
				<p class="text-3xl font-bold text-green-600 mt-1">{(stats.completed_rate * 100).toFixed(1)}%</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
				<p class="text-sm text-gray-500">Средняя позиция</p>
				<p class="text-3xl font-bold text-blue-600 mt-1">{stats.avg_position}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
				<p class="text-sm text-gray-500">Активных проектов</p>
				<p class="text-3xl font-bold text-gray-900 mt-1">{stats.projects_active}</p>
			</div>
		</div>

		<!-- Charts placeholder -->
		<div class="grid grid-cols-2 gap-6">
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
				<h3 class="font-medium text-gray-900 mb-4">Клики по дням</h3>
				<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
					[График кликов — интеграция с D3.js]
				</div>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
				<h3 class="font-medium text-gray-900 mb-4">Гео распределение</h3>
				<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
					[Диаграмма по городам — интеграция с D3.js]
				</div>
			</div>
		</div>

		<!-- Export buttons -->
		<div class="mt-6 flex gap-3">
			<button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
				Экспорт отчёта (CSV)
			</button>
		</div>
	{/if}
</div>
