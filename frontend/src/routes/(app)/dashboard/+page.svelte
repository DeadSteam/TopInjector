<script lang="ts">
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	let activeTab = $state<"overview" | "servers">("overview");
	let dashboardStats = $state<{ overdue: number; today_planned: number; today_completed: number; balance: number }>({
		overdue: 0, today_planned: 0, today_completed: 0, balance: 0
	});
	let serversData = $state<Array<{
		integration: string; label: string; pending: number; speed_per_15min: number; completed_24h: number; hourly_bars: number[];
	}>>([]);
	let loading = $state(true);
	let selectedServer = $state<string | null>(null);

	async function loadAll() {
		loading = true;
		try {
			const [stats, servers] = await Promise.all([
				api.queue.dashboardStats(),
				api.queue.dashboardServers(),
			]);
			dashboardStats = stats;
			serversData = servers || [];
		} catch (err) {
			console.error("Dashboard load failed:", err);
		} finally {
			loading = false;
		}
	}

	let refreshInterval: number | null = null;

	onMount(() => {
		loadAll();
		refreshInterval = window.setInterval(loadAll, 30000);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	function getMaxValue(bars: number[]) {
		const max = Math.max(...bars, 1);
		return max || 1;
	}

	function formatHourlyHours() {
		const now = new Date();
		const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
		const hours: string[] = [];
		for (let i = 0; i < 24; i++) {
			const h = new Date(midnight.getTime() + i * 3600000);
			hours.push(`${String(h.getHours()).padStart(2, '0')}:00`);
		}
		return hours;
	}

	const hourLabels = formatHourlyHours();

	function selectServer(key: string) {
		selectedServer = selectedServer === key ? null : key;
	}
</script>

<div class="p-6">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Сводка</h1>
		<div class="flex items-center gap-3">
			<span class="text-xs text-gray-400">Обновляется каждые 30с</span>
			<button onclick={loadAll} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">Обновить</button>
		</div>
	</div>

	{#if !loading}
		<!-- Stats cards -->
		<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
				<p class="text-xs text-gray-500 mb-1">Выполнено сегодня</p>
				<p class="text-2xl font-bold text-green-600">{dashboardStats.today_completed}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
				<p class="text-xs text-gray-500 mb-1">Просрочено</p>
				<p class="text-2xl font-bold {dashboardStats.overdue > 0 ? 'text-red-600' : 'text-gray-900'}">{dashboardStats.overdue}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
				<p class="text-xs text-gray-500 mb-1">Запланировано</p>
				<p class="text-2xl font-bold text-gray-900">{dashboardStats.today_planned}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
				<p class="text-xs text-gray-500 mb-1">Баланс</p>
				<p class="text-2xl font-bold text-gray-900">{dashboardStats.balance} ₽</p>
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex gap-4 border-b border-gray-200 mb-6">
			<button onclick={() => { activeTab = "overview"; }}
				class="px-4 py-2 text-sm font-medium border-b-2 transition-colors {activeTab === 'overview' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}">
				Обзор
			</button>
			<button onclick={() => { activeTab = "servers"; }}
				class="px-4 py-2 text-sm font-medium border-b-2 transition-colors {activeTab === 'servers' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}">
				Серверы ({serversData.length})
			</button>
		</div>

		<!-- Overview Tab -->
		{#if activeTab === 'overview' && serversData.length > 0}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
				<h3 class="text-base font-semibold text-gray-900 mb-4">Данные по всем интеграциям</h3>

				<!-- Per-server cards with bar charts -->
				<div class="space-y-4">
					{#each serversData as server}
						<div class="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors">
							<div class="flex items-center justify-between mb-3">
								<h4 class="font-semibold text-gray-900">{server.label}</h4>
							</div>

							<!-- Metrics row -->
							<div class="grid grid-cols-4 gap-3 mb-4">
								<div class="bg-gray-50 rounded-lg p-3 text-center">
									<p class="text-xl font-bold {server.pending > 0 ? 'text-red-600' : 'text-gray-900'}">{server.pending}</p>
									<p class="text-xs text-gray-500 mt-1">Ожидают</p>
								</div>
								<div class="bg-gray-50 rounded-lg p-3 text-center">
									<p class="text-xl font-bold text-gray-900">{server.speed_per_15min}</p>
									<p class="text-xs text-gray-500 mt-1">Скорость / 15мин</p>
								</div>
								<div class="bg-gray-50 rounded-lg p-3 text-center">
									<p class="text-xl font-bold text-green-600">{server.completed_24h}</p>
									<p class="text-xs text-gray-500 mt-1">Мои клики</p>
								</div>
								<div class="bg-gray-50 rounded-lg p-3 text-center">
									<p class="text-xl font-bold text-blue-600">{Math.max(server.speed_per_15min * 4, Math.floor(server.completed_24h / 2))}</p>
									<p class="text-xs text-gray-500 mt-1">Остальные клики</p>
								</div>
							</div>

							<!-- Hourly bar chart -->
							<div class="border-t border-gray-100 pt-4">
								<h5 class="text-sm font-medium text-gray-700 mb-3">24-часовая активность</h5>
								<div class="flex items-end gap-px h-32 bg-gray-50 rounded-lg p-2">
									{#each server.hourly_bars as count, hourIdx}
										{#if count > 0}
											<div class="relative flex-1 group" title="{hourLabels[hourIdx]}: {count} кликов">
												<div class="w-full bg-blue-500 hover:bg-blue-600 transition-colors rounded-t-sm cursor-pointer"
													style="height: calc({count / getMaxValue(server.hourly_bars)} * 100%); min-height: 2px;"></div>
											</div>
										{:else}
											<div class="flex-1"></div>
										{/if}
									{/each}
								</div>
								<div class="flex text-xs text-gray-400 mt-1">
									{#each hourLabels as label, idx}
										{#if idx % 3 === 0}
											<span class="flex-1 text-center">{label}</span>
										{:else}
											<span class="flex-1"></span>
										{/if}
									{/each}
								</div>
								<p class="text-xs text-gray-400 mt-3">Неактивные пользователи и проекты не учитываются</p>
							</div>
						</div>
					{/each}
				</div>
			</div>

		<!-- Servers Tab: compact cards -->
		{:else if activeTab === 'servers'}
			<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
				<h3 class="text-base font-semibold text-gray-900 mb-4">Все сервера</h3>
				{#if serversData.length === 0}
					<div class="text-center py-12 text-gray-400">Нет данных о серверах — нет активных проектов</div>
				{:else}
					<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
						{#each serversData as server}
							<div class="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors" onclick={() => selectServer(server.integration)}>
								<h4 class="font-semibold text-gray-900 mb-3">{server.label}</h4>
								<div class="grid grid-cols-2 gap-2">
									<div class="bg-gray-50 rounded p-2 text-center">
										<p class="text-lg font-bold {server.pending > 0 ? 'text-red-600' : 'text-gray-900'}">{server.pending}</p>
										<p class="text-xs text-gray-500">Ожидают</p>
									</div>
									<div class="bg-gray-50 rounded p-2 text-center">
										<p class="text-lg font-bold text-green-600">{server.completed_24h}</p>
										<p class="text-xs text-gray-500">Мои клики</p>
									</div>
									<div class="bg-gray-50 rounded p-2 text-center">
										<p class="text-lg font-bold text-gray-900">{server.speed_per_15min}</p>
										<p class="text-xs text-gray-500">Скорость / 15мин</p>
									</div>
									<div class="bg-gray-50 rounded p-2 text-center">
										<p class="text-lg font-bold text-blue-600">—</p>
										<p class="text-xs text-gray-500">Остальные клики</p>
									</div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	{/if}
</div>
