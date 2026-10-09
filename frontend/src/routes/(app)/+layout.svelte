<script lang="ts">
	import "../app.css";
	import { page } from '$app/stores';
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	let activeRoute = $state("");
	let user = $state<any>(null);

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
	});

	function isActive(path: string): boolean {
		return activeRoute.startsWith(path);
	}

	function getNavItems() {
		return [
			{ path: "/", label: "Проекты", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>' },
			{ path: "/analytics", label: "Аналитика", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>' },
			{ path: "/queue", label: "Очередь", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' },
			{ path: "/settings", label: "Настройки", icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>' },
		];
	}

	function handleLogout() {
		api.auth.logout();
	}
</script>

<div class="flex h-screen overflow-hidden bg-gray-50">
	<!-- Sidebar -->
	<aside class="w-64 flex-shrink-0 bg-[#1e293b] text-white p-4 flex flex-col">
		<div class="text-xl font-bold mb-8 px-2">
			<span class="text-blue-400">Top</span>Injector
		</div>

		<nav class="space-y-1 flex-1">
			{#each getNavItems() as item}
				<a href={item.path} class="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors"
					class:{"bg-white/10 text-white": isActive(item.path)}
					class:{"text-gray-400 hover:text-white hover:bg-white/5": !isActive(item.path)}>
					<div innerHTML={item.icon}></div>
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
	</aside>

	<!-- Main content -->
	<main class="flex-1 overflow-auto">
		<slot />
	</main>
</div>
