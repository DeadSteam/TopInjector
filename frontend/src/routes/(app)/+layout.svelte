<script lang="ts">
	import "../app.css";
	import { page } from '$app/stores';
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	let activeRoute = $state("");
	let user = $state<any>(null);

	// Notifications
	let notifications = $state<any[]>([]);
	let unreadCount = $state(0);
	let showNotifications = $state(false);

	// Global search (Ctrl+E)
	let showGlobalSearch = $state(false);
	let globalQuery = $state("");
	let globalResults = $state({ groups: [] as any[], projects: [] as any[], queries: [] as any[] });
	let searchingGlobal = $state(false);
	let searchDebounce = 0;

	// Dashboard status bar
	let dashboardStats = $state<{ overdue: number; today_planned: number; today_completed: number; balance: number }>({
		overdue: 0, today_planned: 0, today_completed: 0, balance: 0
	});
	let statsLoading = $state(true);

	onMount(async () => {
		const token = localStorage.getItem("token");
		if (!token) {
			window.location.href = "/login";
			return;
		}
		try {
			user = await api.users.profile();
		} catch {
			localStorage.removeItem("token");
			localStorage.removeItem("refresh_token");
			window.location.href = "/login";
		}

		activeRoute = window.location.pathname;
		loadNotifications();
		loadDashboardStats();

		// Global Ctrl+E shortcut
		function onKeydown(e: KeyboardEvent) {
			if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
				e.preventDefault();
				showGlobalSearch = !showGlobalSearch;
			}
			if (e.key === 'Escape' && showGlobalSearch) {
				showGlobalSearch = false;
			}
		}
		document.addEventListener('keydown', onKeydown as any);

		// Cleanup listener is done by Svelte when component is destroyed
	});

	async function loadNotifications() {
		try {
			const data = await api.notifications.list();
			notifications = data.notifications || [];
			unreadCount = (data.notifications || []).filter((n: any) => !n.is_read).length;
		} catch {}
	}

	async function loadDashboardStats() {
		try {
			dashboardStats = await api.queue.dashboardStats();
			statsLoading = false;
		} catch {
			statsLoading = false;
		}
	}

	async function markAllRead() {
		try { await api.notifications.markAllRead(); } catch {}
		unreadCount = 0;
	}

	function isActive(path: string): boolean {
		return activeRoute.startsWith(path);
	}

	function getNavItems() {
		return [
			{ path: "/", label: "Проекты", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>' },
			{ path: "/analytics", label: "Аналитика", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>' },
			{ path: "/queue", label: "Очередь", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
			{ path: "/balance", label: "Баланс", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
			{ path: "/notifications", label: "Уведомления", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>' },
			{ path: "/settings", label: "Настройки", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>' },
		];
	}

	function handleLogout() {
		api.auth.logout();
	}

		async function globalSearchProjects() {
			if (!globalQuery.trim()) {
			globalResults = { groups: [], projects: [], queries: [] };
			return;
			}
			searchingGlobal = true;
			try {
			const res = await api.projects.globalSearch(globalQuery);
			globalResults = res || { groups: [], projects: [], queries: [] };
			} catch {
			globalResults = { groups: [], projects: [], queries: [] };
			}
			searchingGlobal = false;
		}

	function navigateToResult(item: any) {
		if (item.href) {
			window.location.href = item.href;
		}
	}

	onDestroy(() => {
		if (searchDebounce) clearTimeout(searchDebounce);
	});
</script>

<div class="flex h-screen overflow-hidden bg-gray-50">
	<!-- Sidebar -->
	<aside class="w-64 flex-shrink-0 bg-[#1e293b] text-white p-4 flex flex-col relative">
		<div class="text-xl font-bold mb-8 px-2">
			<span class="text-blue-400">Top</span>Injector
		</div>

		<nav class="space-y-1 flex-1">
			{#each getNavItems() as item}
				<a href={item.path} class={(isActive(item.path) ? "bg-white/10 text-white" : "text-gray-400 hover:text-white hover:bg-white/5") + " flex items-center gap-3 px-3 py-2 rounded-lg transition-colors"}>
					<span>{@html item.icon}</span>
					<span>{item.label}</span>
				</a>
			{/each}
		</nav>

		<!-- User info -->
		<div class="mt-auto pt-4 border-t border-white/10">
			{#if user}
				<div class="flex items-center gap-3 px-3 py-2">
					<div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-sm font-bold">
						{(user.display_name || user.email || "U").charAt(0).toUpperCase()}
					</div>
					<div class="flex-1 min-w-0">
						<p class="text-sm truncate">{user.display_name || "User"}</p>
						<p class="text-xs text-gray-400 truncate">{user.email}</p>
					</div>
				</div>
			{/if}
			<button onclick={handleLogout} class="w-full mt-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
				Выйти
			</button>
		</div>

		<!-- Notification bell (links to notifications page) -->
		<a href="/notifications" class="absolute top-4 right-4 p-2 rounded-lg hover:bg-white/10 transition-colors relative block" title="Уведомления">
			<svg class="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
			</svg>
			{#if unreadCount > 0}
				<span class="absolute top-1 right-1 w-2.5 h-2.5 bg-red-500 rounded-full"></span>
			{/if}
		</a>
	</aside>

	<!-- Main content -->
	<main class="flex-1 overflow-auto relative">
		<!-- Status bar — thin strip above page content -->
		<div class="flex items-center gap-4 px-4 py-1.5 bg-white border-b border-gray-200 text-xs flex-wrap">
			{#if statsLoading}
				<span class="text-gray-400">Загрузка...</span>
			{:else}
				<!-- Overdue counter -->
				<a href="/queue" class="flex items-center gap-1.5 px-2 py-0.5 rounded-full font-medium transition-colors {dashboardStats.overdue > 0 ? 'bg-red-50 text-red-700 hover:bg-red-100' : 'text-gray-400'}">
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
					Просрочено: {dashboardStats.overdue}
				</a>

				<!-- Today clicks -->
				<span class="flex items-center gap-1.5 text-gray-400">
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0v8m0-8l-8 8-4-4-6 6"/></svg>
					Сегодня: {dashboardStats.today_completed} / {dashboardStats.today_planned} кликов
				</span>

				<!-- Balance -->
				<span class="flex items-center gap-1.5 text-gray-400">
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
					Баланс: {dashboardStats.balance} ₽
				</span>

				<!-- Spacer -->
				<span class="flex-1"></span>
			{/if}
		</div>

		<slot />

		<!-- Global search modal (Ctrl+E) -->
		{#if showGlobalSearch}
			<div class="fixed inset-0 bg-black/40 flex items-start justify-center z-50 pt-24 px-4" onclick={(e) => { if (e.target === e.currentTarget) showGlobalSearch = false; }}>
				<div class="bg-white rounded-xl shadow-2xl w-full max-w-xl overflow-hidden">
					<!-- Search input -->
					<div class="flex items-center gap-3 px-4 py-3 border-b border-gray-200">
						<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
						</svg>
						<input type="text" bind:value={globalQuery} placeholder="Глобальный поиск..." class="flex-1 text-base outline-none" oninput={globalSearchProjects} />
						<span class="text-xs text-gray-400 border border-gray-300 rounded px-1.5 py-0.5">Esc</span>
					</div>

					<!-- Results -->
					<div class="max-h-80 overflow-y-auto">
						{#if searchingGlobal}
							<div class="px-4 py-3 text-sm text-gray-400 text-center">Search...</div>
						{:else if !globalQuery.trim()}
							<div class="px-4 py-3 text-sm text-gray-400 text-center">Введите минимум 2 символа</div>
						{:else}

						{#if globalResults.groups && globalResults.groups.length > 0}
							<div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Группы</div>
							{#each globalResults.groups as g}
								<a href={g.href} class="block px-4 py-2 hover:bg-blue-50 transition-colors">
									<div class="flex items-center gap-3">
										<span class="text-gray-500"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2 2z"/></svg></span>
										<div><p class="text-sm font-medium text-gray-900">{g.label}</p><p class="text-xs text-gray-500">Группа</p></div>
									</div>
								</a>
							{/each}
						{/if}

						{#if globalResults.projects && globalResults.projects.length > 0}
							<div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Проекты</div>
							{#each globalResults.projects as p}
								<a href={p.href} class="block px-4 py-2 hover:bg-blue-50 transition-colors">
									<div class="flex items-center gap-3">
										<span class="text-blue-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg></span>
										<div><p class="text-sm font-medium text-gray-900">{p.label}</p><p class="text-xs text-gray-500">{p.sub}</p></div>
									</div>
								</a>
							{/each}
						{/if}

						{#if globalResults.queries && globalResults.queries.length > 0}
							<div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Запросы</div>
							{#each globalResults.queries as q}
								<a href={q.href} class="block px-4 py-2 hover:bg-blue-50 transition-colors">
									<div class="flex items-center gap-3">
										<span class="text-yellow-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2m-6 4h6a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V10a2 2 0 012-2z"/></svg></span>
										<div><p class="text-sm font-medium text-gray-900">{q.label}</p><p class="text-xs text-gray-500">{q.sub}</p></div>
									</div>
								</a>
							{/each}
						{/if}

						{#if globalResults.groups.length === 0 && globalResults.projects.length === 0 && globalResults.queries.length === 0}
							<div class="px-4 py-3 text-sm text-gray-400 text-center">Ничего не найдено</div>
						{/if}
					{/if}
				</div>

				{#if !globalQuery.trim()}
					<div class="px-4 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-400">
						<p>Нажмите <kbd class="px-1.5 py-0.5 bg-white border border-gray-300 rounded text-[10px] font-mono">Ctrl+E</kbd> для поиска.</p>
					</div>
				{/if}
				</div>
			</div>
		{/if}
	</main>
</div>
