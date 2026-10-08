<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	let profile = $state<any>(null);
	let apiTokens = $state<any[]>([]);
	let loading = $state(true);
	let error = $state("");
	let newName = $state("");
	let newTokenName = $state("");
	let copiedToken = $state("");

	async function loadSettings() {
		try {
			profile = await api.users.profile();
			apiTokens = await api.users.apiTokens();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка загрузки";
		} finally {
			loading = false;
		}
	}

	async function updateProfile() {
		if (!newName.trim()) return;
		try {
			await api.users.updateProfile({ display_name: newName });
			await loadSettings();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка сохранения";
		}
	}

	async function createToken() {
		if (!newTokenName.trim()) return;
		try {
			const res = await api.users.createToken(newTokenName);
			apiTokens = [...apiTokens, res];
			copiedToken = res.token;
			localStorage.setItem("external_token", res.token);
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка создания токена";
		}
	}

	function copyToken(token: string) {
		navigator.clipboard.writeText(token);
		copiedToken = token;
		setTimeout(() => (copiedToken = ""), 2000);
	}

	onMount(() => { loadSettings(); });
</script>

<div class="p-6">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Настройки</h1>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else if profile}
		<div class="grid grid-cols-2 gap-6">
			<!-- Profile settings -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Профиль</h2>
				<form onsubmit={(e) => { e.preventDefault(); updateProfile(); }} class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Имя</label>
						<input type="text" bind:value={newName} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
						<input type="email" value={profile.email} disabled class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm" />
					</div>
					<button type="submit" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">Сохранить</button>
				</form>
			</div>

			<!-- Integration settings -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Интеграции</h2>
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Яндекс Метрика — ID счётчика</label>
						<input type="text" placeholder="123456789" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Яндекс Вебмастер — ID проекта</label>
						<input type="text" placeholder="" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
					</div>
				</div>
			</div>

			<!-- API Tokens -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">API Токены</h2>
				<p class="text-sm text-gray-500 mb-3">Используется для авторизации ботов и внешних сервисов (X-Auth-Token).</p>

				<form onsubmit={(e) => { e.preventDefault(); createToken(); }} class="flex gap-2 mb-4">
					<input type="text" bind:value={newTokenName} placeholder="Название токена" class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				 <button type="submit" class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">Создать</button>
				</form>

				{#if apiTokens.length > 0}
					<div class="space-y-2">
						{#each apiTokens as token}
							<div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
								<div>
									<p class="text-sm font-medium">{token.name}</p>
									<p class="text-xs font-mono text-gray-500">{token.token || token.id}</p>
								</div>
								<button onclick={() => copyToken(token.token || token.id)} class="px-3 py-1 border border-gray-300 rounded-lg text-xs hover:bg-gray-100 transition-colors">
									{copiedToken === (token.token || token.id) ? 'Скопировано!' : 'Копировать'}
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Plan -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Тарифный план</h2>
				<div class="space-y-3">
					<div class="flex justify-between items-center">
						<span class="text-sm text-gray-600">Текущий план</span>
						<span class="font-medium text-gray-900">{profile.plan || "free"}</span>
					</div>
					<div class="flex justify-between items-center">
						<span class="text-sm text-gray-600">Кликов/день</span>
						<span class="font-medium text-gray-900">{profile.daily_limit || 150}</span>
					</div>
					<div class="flex justify-between items-center">
						<span class="text-sm text-gray-600">Баланс</span>
						<span class="font-medium text-green-600">{profile.balance || 0} ₽</span>
					</div>
					<button class="w-full mt-2 px-4 py-2 border border-blue-600 text-blue-600 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors">
						Изменить план
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
