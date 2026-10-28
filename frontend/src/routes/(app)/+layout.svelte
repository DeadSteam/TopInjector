<script lang="ts">
	import "../../app.css";
	import { page } from '$app/state';
	import { afterNavigate } from '$app/navigation';
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	let { children } = $props();

	// Below md the sidebar is a drawer opened from the top bar
	let sidebarOpen = $state(false);
	afterNavigate(() => { sidebarOpen = false; });

	let user = $state<any>(null);

	// Notifications
	let notifications = $state<any[]>([]);
	let unreadCount = $state(0);
	let showNotifications = $state(false);

	// Global search (Ctrl+E)
	let showGlobalSearch = $state(false);
	let globalQuery = $state("");
	let globalResults = $state<{ groups: any[], projects: any[], queries: any[] }>({ groups: [], projects: [], queries: [] });
	let searchingGlobal = $state(false);
	let searchDebounce = 0;

	// Server groups (integrations sidebar)
	let serverIntegrations = $state<Array<{ key: string; label: string }>>([]);
	let collapsedGroups = $state<Record<string, boolean>>({});
	let selectedIntegration = $state<string | null>(null);

	function collapseToggle(key: string) {
		collapsedGroups = { ...collapsedGroups, [key]: !collapsedGroups[key] };
	}

	async function loadServerIntegrations() {
		try {
			const data = await api.projects.integrations();
			serverIntegrations = (data.integrations || [])
				.filter((i: any) => i.key !== "default")
				.map((i: any) => ({ key: i.key, label: i.label }));
			const collapsed: Record<string, boolean> = {};
			serverIntegrations.forEach((integ: any) => { collapsed[integ.key] = true; });
			collapsedGroups = collapsed;
		} catch { serverIntegrations = []; }
	}

	function selectIntegrationFilter(key: string) {
		const url = new URL(window.location.href);
		if (key === selectedIntegration) {
			url.searchParams.delete('integration_type');
			selectedIntegration = null;
		} else {
			url.searchParams.set('integration_type', key);
			selectedIntegration = key;
		}
		window.location.href = url.toString();
	}

	// Dashboard status bar
	let dashboardStats = $state<{ overdue: number; today_planned: number; today_completed: number; balance: number }>({
		overdue: 0, today_planned: 0, today_completed: 0, balance: 0
	});
	let statsLoading = $state(true);

	// Intervals for background updates (declared at component scope to avoid Svelte 5 onDestroy issue)
	let statsIntervalId = 0;
	let notifIntervalId = 0;

	function onKeydown(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && e.key === 'e') { e.preventDefault(); showGlobalSearch = !showGlobalSearch; }
		if (e.key === 'Escape' && showGlobalSearch) { showGlobalSearch = false; }
	}

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

		await loadServerIntegrations();

		loadNotifications();
		loadDashboardStats();

		statsIntervalId = window.setInterval(loadDashboardStats, 30000);
		notifIntervalId = window.setInterval(async () => { try { await loadNotifications(); } catch {} }, 30000);
	});

	async function loadNotifications() {
		try {
			const data = await api.notifications.list();
			notifications = data.notifications || [];
			unreadCount = (data.notifications || []).filter((n: any) => !n.is_read).length;
		} catch {}
	}

	async function loadDashboardStats() {
		try { dashboardStats = await api.queue.dashboardStats(); statsLoading = false; }
		catch { statsLoading = false; }
	}

	async function markAllRead() { try { await api.notifications.markAllRead(); } catch {} unreadCount = 0; }

	function isActive(path: string): boolean {
		const current = page.url.pathname;
		// "Проекты" (/) also covers project detail pages; other items match by prefix
		if (path === "/") return current === "/" || current.startsWith("/projects");
		return current.startsWith(path);
	}

	function getNavItems() {
		return [
			{ path: "/dashboard", label: "Сводка", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/></svg>' },
			{ path: "/", label: "Проекты", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>' },
			{ path: "/analytics", label: "Аналитика", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>' },
			{ path: "/queue", label: "Очередь", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
			{ path: "/warmups", label: "Разогрев", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"/></svg>' },
			{ path: "/balance", label: "Баланс", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
			{ path: "/plan", label: "Тариф", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5a1.99 1.99 0 011.414.586l7 7a2 2 0 010 2.828l-5 5a2 2 0 01-2.828 0l-7-7A1.99 1.99 0 013 10V5a2 2 0 012-2z"/></svg>' },
			{ path: "/external-services", label: "Внешние сервисы", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>' },
			{ path: "/branding", label: "Брендинг", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"/></svg>' },
			{ path: "/settings/integrations", label: "Интеграции", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 8a2 2 0 00-2-2v12a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v3m0 0v3a2 2 0 002 2h2a2 2 0 002-2V9a2 2 0 00-2-2h-2" /></svg>' },
			{ path: "/notifications", label: "Уведомления", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>' },
			{ path: "/settings", label: "Настройки", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>' },
		];
	}

	function handleLogout() { api.auth.logout(); }

	async function globalSearchProjects() {
		if (!globalQuery.trim()) { globalResults = { groups: [], projects: [], queries: [] }; return; }
		searchingGlobal = true;
		try { const res = await api.projects.globalSearch(globalQuery); globalResults = res || { groups: [], projects: [], queries: [] }; }
		catch { globalResults = { groups: [], projects: [], queries: [] }; }
		searchingGlobal = false;
	}

	function navigateToResult(item: any) { if (item.href) window.location.href = item.href; }

	onDestroy(() => { if (searchDebounce) clearTimeout(searchDebounce); clearInterval(statsIntervalId); clearInterval(notifIntervalId); });
</script>

<svelte:document onkeydown={onKeydown} />

<div class="flex h-screen overflow-hidden bg-gray-50">
	<!-- Sidebar -->
	{#if sidebarOpen}
		<div class="fixed inset-0 bg-black/40 z-30 md:hidden" onclick={() => (sidebarOpen = false)} aria-hidden="true"></div>
	{/if}
	<aside class="w-64 flex-shrink-0 bg-[#1e293b] text-white p-4 flex flex-col fixed inset-y-0 left-0 z-40 overflow-y-auto transition-transform md:relative md:translate-x-0 {sidebarOpen ? 'translate-x-0' : '-translate-x-full'}">
		<div class="text-xl font-bold mb-8 px-2"><span class="text-blue-400">Top</span>Injector</div>

		<nav class="space-y-1 flex-1">
			{#each getNavItems() as item}
				<a href={item.path} class={(isActive(item.path) ? "bg-white/10 text-white" : "text-gray-400 hover:text-white hover:bg-white/5") + " flex items-center gap-3 px-3 py-2 rounded-lg transition-colors"}>
					<span>{@html item.icon}</span><span>{item.label}</span>
				</a>
			{/each}
		</nav>

		<!-- Server groups (integrations sidebar) -->
		{#if serverIntegrations.length > 0}
			<div class="mt-4 pt-3 border-t border-white/10">
				<p class="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Серверы</p>
				{#each serverIntegrations as integ}
					<div>
						<button onclick={() => collapseToggle(integ.key)} class="w-full flex items-center gap-3 px-3 py-1.5 rounded-lg transition-colors text-gray-400 hover:text-white hover:bg-white/5">
							<svg class="w-3.5 h-3.5 transition-transform {collapsedGroups[integ.key] ? '' : 'rotate-90'}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
							<span class="text-sm truncate flex-1 text-left">{integ.label}</span>
						</button>
						{#if !collapsedGroups[integ.key]}
							<div class="ml-7 mt-0.5 space-y-0.5">
								<button onclick={() => selectIntegrationFilter(integ.key)} class="w-full flex items-center gap-2 px-3 py-1 rounded-md text-xs transition-colors {selectedIntegration === integ.key ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-white hover:bg-white/5'}">
									<span class="inline-block w-4">{selectedIntegration === integ.key ? '✓' : '›'}</span> Все проекты
								</button>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		<!-- User info -->
		<div class="mt-auto pt-4 border-t border-white/10">
			{#if user}
				<div class="flex items-center gap-3 px-3 py-2">
					<div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-sm font-bold">{(user.display_name || user.email || "U").charAt(0).toUpperCase()}</div>
					<div class="flex-1 min-w-0"><p class="text-sm truncate">{user.display_name || "User"}</p><p class="text-xs text-gray-400 truncate">{user.email}</p></div>
				</div>
			{/if}
			<button onclick={handleLogout} class="w-full mt-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors">Выйти</button>
		</div>

		<a href="/notifications" class="absolute top-4 right-4 p-2 rounded-lg hover:bg-white/10 transition-colors block" title="Уведомления">
			<svg class="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>
			{#if unreadCount > 0}<span class="absolute top-1 right-1 w-2.5 h-2.5 bg-red-500 rounded-full"></span>{/if}
		</a>
	</aside>

	<main class="flex-1 min-w-0 overflow-auto relative">
		<div class="flex items-center gap-4 px-4 py-1.5 bg-white border-b border-gray-200 text-xs flex-wrap">
			<button onclick={() => (sidebarOpen = true)} class="md:hidden -ml-1 p-1.5 rounded-lg text-gray-600 hover:bg-gray-100" aria-label="Открыть меню">
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>
			</button>
			{#if statsLoading}<span class="text-gray-400">Загрузка...</span>
			{:else}
				<a href="/queue" class="flex items-center gap-1.5 px-2 py-0.5 rounded-full font-medium transition-colors {dashboardStats.overdue > 0 ? 'bg-red-50 text-red-700 hover:bg-red-100' : 'text-gray-400'}">
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Просрочено: {dashboardStats.overdue}
				</a>
				<span class="flex items-center gap-1.5 text-gray-400"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0v8m0-8l-8 8-4-4-6 6"/></svg> Сегодня: {dashboardStats.today_completed} / {dashboardStats.today_planned} кликов</span>
				<span class="flex items-center gap-1.5 text-gray-400"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Баланс: {dashboardStats.balance} ₽</span>
				<span class="flex-1"></span>
			{/if}
		</div>

		{@render children()}

		{#if showGlobalSearch}
			<div class="fixed inset-0 bg-black/40 flex items-start justify-center z-50 pt-24 px-4" onclick={(e) => { if (e.target === e.currentTarget) showGlobalSearch = false; }}>
				<div class="bg-white rounded-xl shadow-2xl w-full max-w-xl overflow-hidden">
					<div class="flex items-center gap-3 px-4 py-3 border-b border-gray-200">
						<svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
						<input type="text" bind:value={globalQuery} placeholder="Глобальный поиск..." class="flex-1 text-base outline-none" oninput={globalSearchProjects} />
						<span class="text-xs text-gray-400 border border-gray-300 rounded px-1.5 py-0.5">Esc</span>
					</div>
					<div class="max-h-80 overflow-y-auto">
						{#if searchingGlobal}<div class="px-4 py-3 text-sm text-gray-400 text-center">Поиск…</div>
						{:else if !globalQuery.trim()}<div class="px-4 py-3 text-sm text-gray-400 text-center">Введите минимум 2 символа</div>
						{:else}
							{#if globalResults.groups && globalResults.groups.length > 0}
								<div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Группы</div>
								{#each globalResults.groups as g}
									<a href={g.href} data-sveltekit-reload class="block px-4 py-2 hover:bg-blue-50 transition-colors">
										<div class="flex items-center gap-3"><span class="text-gray-500"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2 2z"/></svg></span><div><p class="text-sm font-medium text-gray-900">{g.name}</p><p class="text-xs text-gray-500">Группа</p></div></div>
									</a>
								{/each}
							{/if}
							{#if globalResults.projects && globalResults.projects.length > 0}
								<div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Проекты</div>
								{#each globalResults.projects as p}
									<a href={p.href} data-sveltekit-reload class="block px-4 py-2 hover:bg-blue-50 transition-colors">
										<div class="flex items-center gap-3"><span class="text-blue-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg></span><div><p class="text-sm font-medium text-gray-900">{p.name}</p><p class="text-xs text-gray-500">{p.domain}</p></div></div>
									</a>
								{/each}
							{/if}
							{#if globalResults.queries && globalResults.queries.length > 0}
								<div class="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Запросы</div>
								{#each globalResults.queries as q}
									<a href={q.href} data-sveltekit-reload class="block px-4 py-2 hover:bg-blue-50 transition-colors">
										<div class="flex items-center gap-3"><span class="text-yellow-600"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 4V2a1 1 0 011-1h8a1 1 0 011 1v2m-6 4h6a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V10a2 2 0 012-2z"/></svg></span><div><p class="text-sm font-medium text-gray-900">{q.text}</p><p class="text-xs text-gray-500">{q.project_name}</p></div></div>
									</a>
								{/each}
							{/if}
							{#if globalResults.groups.length === 0 && globalResults.projects.length === 0 && globalResults.queries.length === 0}
								<div class="px-4 py-3 text-sm text-gray-400 text-center">Ничего не найдено</div>
							{/if}
						{/if}
					</div>
					{#if !globalQuery.trim()}<div class="px-4 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-400"><p>Нажмите <kbd class="px-1.5 py-0.5 bg-white border border-gray-300 rounded text-[10px] font-mono">Ctrl+E</kbd> для поиска.</p></div>{/if}
				</div>
			</div>
		{/if}
	</main>
</div>
