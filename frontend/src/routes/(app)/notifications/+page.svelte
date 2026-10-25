<script lang="ts">
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	let notifications = $state<any[]>([]);
	let loading = $state(true);
	let markingRead = $state<string | null>(null);
	let markingAllRead = $state(false);
	let error = $state("");
	let filter = $state<"all" | "unread">("all");
	let refreshInterval = 0;

	async function loadNotifications() {
		try {
			const data = await api.notifications.list();
			notifications = data.notifications || [];
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки уведомлений";
		} finally {
			loading = false;
		}
	}

	async function markAsRead(id: string) {
		markingRead = id;
		try {
			await api.notifications.markRead(id);
			const idx = notifications.findIndex(n => n.id === id);
			if (idx !== -1) {
				notifications[idx] = { ...notifications[idx], is_read: true };
			}
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка чтения"; }
		markingRead = null;
	}

	async function markAllReadAction() {
		markingAllRead = true;
		try {
			await api.notifications.markAllRead();
			notifications = notifications.map(n => ({ ...n, is_read: true }));
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка при отметке всех"; }
		markingAllRead = false;
	}

	function getNotificationIcon(n: any): string {
		const body = n.body || n.title || "";
		if (body.includes("задача") || body.includes("task") || n.title?.includes("Очередь")) return "📨";
		if (body.includes("ошибка") || body.includes("error") || n.title?.includes("Ошибка")) return "❌";
		if (body.includes("баланс") || body.includes("balance")) return "💰";
		if (body.includes("проект") || body.includes("project")) return "📁";
		if (body.includes("запрос") || body.includes("query")) return "🔍";
		return "🔔";
	}

	function timeAgo(dateStr: string): string {
		const diff = Date.now() - new Date(dateStr).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return "только что";
		if (mins < 60) return `${mins} мин. назад`;
	 const hours = Math.floor(mins / 60);
		if (hours < 24) return `${hours} ч. назад`;
		const days = Math.floor(hours / 24);
		return `${days} д. назад`;
	}

	// Auto-refresh every 30 seconds
	onMount(() => {
		loadNotifications();
		refreshInterval = window.setInterval(loadNotifications, 30000);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	// Computed filtered list using Svelte $derived
	let filteredNotifications = $derived(filter === "unread"
		? notifications.filter(n => !n.is_read)
		: [...notifications]);
</script>

<div class="p-6">
	<div class="flex flex-wrap items-center justify-between gap-3 mb-6">
		<h1 class="text-2xl font-bold text-gray-900">Уведомления</h1>
		{#if notifications.some(n => !n.is_read)}
			<button onclick={markAllReadAction} disabled={markingAllRead} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors">
				{markingAllRead ? 'Отметка…' : 'Прочитать все'}
			</button>
		{/if}
	</div>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	<!-- Filter tabs -->
	<div class="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
		<button onclick={() => filter = "all"} class={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${filter === 'all' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
			Все
		</button>
		<button onclick={() => filter = "unread"} class={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${filter === 'unread' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
			Непрочитанные
		</button>
	</div>

	{#if loading}
		<div class="text-center py-12">
			<svg class="w-12 h-12 text-gray-300 mx-auto mb-3 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
			</svg>
			<p class="text-sm text-gray-400">Загрузка...</p>
		</div>
	{:else}

		{#if filteredNotifications.length === 0}
			<div class="text-center py-12 bg-white border border-gray-200 rounded-xl shadow-sm">
				<svg class="w-16 h-16 text-gray-200 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
				</svg>
				<p class="text-sm text-gray-400 font-medium">Нет уведомлений</p>
				<p class="text-xs text-gray-300 mt-1">Уведомления будут появляться здесь</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each filteredNotifications as n, idx}
					<div class={`flex items-start gap-3 p-4 rounded-xl border transition-all hover:shadow-sm ${n.is_read ? 'bg-white border-gray-100' : 'bg-blue-50 border-blue-100 ring-1 ring-blue-100'}`}>
						<!-- Icon -->
						<div class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-base mt-0.5">
							{getNotificationIcon(n)}
						</div>

						<!-- Content -->
						<div class="flex-1 min-w-0">
							<div class="flex items-start justify-between gap-2">
								<p class="text-sm font-semibold text-gray-900 {n.is_read ? '' : ''}">{n.title || 'Уведомление'}</p>
								{#if !n.is_read}
									<button
										onclick={() => markAsRead(n.id)}
										disabled={markingRead === n.id}
										class="flex-shrink-0 px-2 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-md text-xs font-medium transition-colors whitespace-nowrap"
									>
										{markingRead === n.id ? '...' : 'Прочитать'}
									</button>
								{/if}
							</div>
							{#if n.body}
								<p class="text-sm text-gray-600 mt-1 leading-relaxed">{n.body}</p>
							{/if}
							<p class="text-xs text-gray-400 mt-2">{timeAgo(n.created_at)}</p>
						</div>

						<!-- Unread indicator -->
						{#if !n.is_read}
							<div class="flex-shrink-0 mt-2">
								<div class="w-2 h-2 rounded-full bg-blue-500"></div>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>
