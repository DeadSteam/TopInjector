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

	// Messenger settings
	let telegramWebhookUrl = $state("");
	let maxConnectorId = $state("");
	let messengerLoading = $state(false);
	let messengerSaved = $state(false);

	// External services
	let xmlRiverUserId = $state("");
	let xmlRiverApk = $state("");
	let xmlStockEntries: Array<{ name: string; api_key: string }> = $state([]);
	let externalLoading = $state(false);
	let externalSaved = $state(false);

	// Password change
	let currentPassword = $state("");
	let avatarUrl = $state("");
	let newPassword = $state("");
	let confirmNewPassword = $state("");
	let passwordChanged = $state(false);

	// Stop words management
	let stopWords = $state<string[]>([]);
	let newStopWord = $state("");

	// Admin panel stats
	let adminStats = $state<{ total_users: number; total_projects: number; active_projects: number; total_balance_credits: number; queue_tasks: Record<string, number> }>({
		total_users: 0, total_projects: 0, active_projects: 0, total_balance_credits: 0, queue_tasks: {}
	});
	let loadingAdmin = $state(true);

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

	async function deleteUserToken(id: string, tokenStr: string) {
		if (!confirm("Удалить этот токен?")) return;
		try {
			await api.users.deleteToken(id);
			apiTokens = apiTokens.filter(t => t.id !== id);
			copiedToken = copiedToken === tokenStr ? "" : copiedToken;
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка удаления токена";
		}
	}

	onMount(() => { loadSettings(); });

	async function loadMessenger() {
		try {
			const data = await api.users.messengerSettings();
			telegramWebhookUrl = data.telegram_webhook_url || "";
			maxConnectorId = data.max_connector_id || "";
		} catch {}
	}

	async function saveMessenger() {
		messengerLoading = true;
		try {
			await api.users.updateMessengerSettings({
				telegram_webhook_url: telegramWebhookUrl,
				max_connector_id: maxConnectorId,
			});
			messengerSaved = true;
			setTimeout(() => { messengerSaved = false; }, 3000);
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка сохранения"; }
		messengerLoading = false;
	}

	async function loadExternalServices() {
		try {
			const data = await api.users.externalServices();
			xmlRiverUserId = data.xml_river?.user_id || "";
			xmlRiverApk = data.xml_river?.apk || "";
			xmlStockEntries = data.xml_stock || [{ name: "", api_key: "" }];
		} catch {}
	}

	async function saveExternalServices() {
		externalLoading = true;
		try {
			const xmlRiver = (xmlRiverUserId || xmlRiverApk) ? { user_id: xmlRiverUserId, apk: xmlRiverApk } : null;
			const stock = xmlStockEntries.filter(e => e.name.trim());
			await api.users.updateExternalServices({ xml_river: xmlRiver || undefined, xml_stock: stock });
			externalSaved = true;
			setTimeout(() => { externalSaved = false; }, 3000);
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка сохранения"; }
		externalLoading = false;
	}

	function addStockEntry() { xmlStockEntries = [...xmlStockEntries, { name: "", api_key: "" }]; }
	function removeStockEntry(i: number) { xmlStockEntries.splice(i, 1); }

	async function changePassword() {
		if (newPassword !== confirmNewPassword) { error = "Пароли не совпадают"; return; }
		try {
			await api.users.changePassword({ current_password: currentPassword, new_password: newPassword });
			passwordChanged = true;
			currentPassword = ""; newPassword = ""; confirmNewPassword = "";
			setTimeout(() => { passwordChanged = false; }, 3000);
		} catch (err) { error = err instanceof Error ? err.message : "Ошибка смены пароля"; }
	}

	async function loadStopWords() {
		try { const data = await api.users.stopWords(); stopWords = data.stop_words || []; } catch {}
	}

	async function addStopWord() {
		if (!newStopWord.trim()) return;
		const existing = newStopWord.toLowerCase().trim();
		if (stopWords.includes(existing)) return;
		const res: any = await api.users.addStopWord(newStopWord.trim());
		stopWords = res.stop_words || [];
		newStopWord = "";
	}

	async function removeStopWord(word: string) {
		await api.users.removeStopWord(word);
		stopWords = stopWords.filter(w => w !== word);
	}

	async function loadAdminStats() {
		try {
			const stats = await api.projects.adminStats();
			adminStats = stats;
		} catch {} finally { loadingAdmin = false; }
	}

	onMount(() => { loadStopWords(); loadAdminStats(); });
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

			<!-- Messenger integration -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">

			<!-- Avatar Section -->
			<div class="border-t border-gray-200 pt-6 mt-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Аватар профиля</h2>
				{#if profile && profile.avatar_url}
					<div class="flex items-center gap-4">
						<img src={profile.avatar_url} alt="Avatar" class="w-16 h-16 rounded-full object-cover border-2 border-gray-200" />
						<div>
							<p class="text-sm text-gray-600">Аватар загружен</p>
							<button
								onclick={async () => {
									try { await api.users.deleteAvatar(); profile.avatar_url = null; } catch(e) { console.error("Delete avatar failed:", e); }
								}}
								class="mt-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs rounded-lg transition-colors">
								Удалить аватар
							</button>
						</div>
					</div>
				{:else}
					<p class="text-sm text-gray-500 mb-3">У вас нет аватара. Укажите URL изображения для загрузки.</p>
					<div class="flex gap-2 items-end">
						<input type="url" bind:value={avatarUrl} placeholder="https://example.com/avatar.jpg"
							class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
						<button
							onclick={async () => {
								if (!avatarUrl.trim()) return;
								try { await api.users.uploadAvatar({ avatar_url: avatarUrl }); profile.avatar_url = avatarUrl; avatarUrl = ""; }
								catch(e) { console.error("Upload avatar failed:", e); }
							}}
							class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors">
							Загрузить
						</button>
					</div>
				{/if}
			</div>
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Мессенджеры</h2>
				{#if messengerSaved}
					<div class="mb-3 p-2 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">Сохранено</div>
				{/if}
				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Telegram — Webhook URL</label>
						<input type="url" bind:value={telegramWebhookUrl} placeholder="https://your-bot.example.com/webhook" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
						<p class="text-xs text-gray-400 mt-1">URL для получения webhook уведомлений от Telegram бота</p>
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Max — Connector ID</label>
						<input type="text" bind:value={maxConnectorId} placeholder="connector-uuid" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
						<p class="text-xs text-gray-400 mt-1">ID коннектора для интеграции с Max</p>
					</div>
					<button onclick={saveMessenger} disabled={messengerLoading} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors">
						{messengerLoading ? 'Сохранение…' : 'Сохранить'}
					</button>
				</div>
			</div>

			<!-- External services -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Внешние сервисы</h2>
				{#if externalSaved}
					<div class="mb-3 p-2 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">Сохранено</div>
				{/if}

				<!-- XML River -->
				<div class="mb-6">
					<h3 class="text-sm font-medium text-gray-900 mb-2">XML River</h3>
					<p class="text-xs text-gray-400 mb-3">UserID + APK для XML River прокси</p>
					<div class="space-y-2">
						<div>
							<label class="block text-xs text-gray-500 mb-1">User ID</label>
							<input type="text" bind:value={xmlRiverUserId} placeholder="your-user-id" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
						<div>
							<label class="block text-xs text-gray-500 mb-1">APK</label>
							<input type="text" bind:value={xmlRiverApk} placeholder="your-apk-key" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
						</div>
					</div>
				</div>

				<!-- XML Stock -->
				<div>
					<h3 class="text-sm font-medium text-gray-900 mb-2">XML Stock</h3>
					<p class="text-xs text-gray-400 mb-3">Множественные ключи API</p>
					{#each xmlStockEntries as entry, i}
						<div class="flex gap-2 mb-2 items-start">
							<input type="text" bind:value={entry.name} placeholder="Имя ключа" class="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
							<input type="text" bind:value={entry.api_key} placeholder="API Key" class="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
							<button onclick={() => removeStockEntry(i)} class="px-2 py-1.5 text-red-500 hover:bg-red-50 rounded-lg text-xs">Удалить</button>
						</div>
					{/each}
					<button onclick={addStockEntry} class="px-3 py-1.5 border border-dashed border-gray-300 text-gray-500 hover:text-gray-700 hover:border-gray-400 rounded-lg text-xs transition-colors">+ Добавить ключ</button>
				</div>

				<button onclick={saveExternalServices} disabled={externalLoading} class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors">
					{externalLoading ? 'Сохранение…' : 'Сохранить'}
				</button>
			</div>

			<!-- Password change -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Смена пароля</h2>
				{#if passwordChanged}
					<div class="mb-3 p-2 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700">Пароль успешно изменён</div>
				{/if}
				<form onsubmit={(e) => { e.preventDefault(); changePassword(); }} class="space-y-3">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Текущий пароль</label>
						<input type="password" bind:value={currentPassword} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Новый пароль</label>
						<input type="password" bind:value={newPassword} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
					</div>
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Подтвердите новый пароль</label>
						<input type="password" bind:value={confirmNewPassword} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
					</div>
					<button type="submit" class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors">Сменить пароль</button>
				</form>
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
								<div class="flex gap-2">
									<button onclick={() => copyToken(token.token || token.id)} class="px-3 py-1 border border-gray-300 rounded-lg text-xs hover:bg-gray-100 transition-colors">
										{copiedToken === (token.token || token.id) ? 'Скопировано!' : 'Копировать'}
									</button>
									<button onclick={() => deleteUserToken(token.id, token.token || token.id)} class="px-3 py-1 border border-red-300 text-red-600 rounded-lg text-xs hover:bg-red-50 transition-colors">Удалить</button>
								</div>
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

			<!-- Stop words management -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Словофильтр (стоп-слова)</h2>
				<p class="text-sm text-gray-500 mb-3">Запросы, содержащие эти слова, исключаются из генерации задач.</p>

				<form onsubmit={(e) => { e.preventDefault(); addStopWord(); }} class="flex gap-2 mb-4">
					<input type="text" bind:value={newStopWord} placeholder="Введите стоп-слово..." class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				 <button type="submit" disabled={stopWords.includes(newStopWord.toLowerCase().trim())} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-lg text-sm font-medium transition-colors">Добавить</button>
				</form>

				{#if stopWords.length > 0}
					<div class="space-y-2">
						{#each stopWords as word}
							<div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
								<code class="text-sm text-gray-700">{word}</code>
								<button onclick={() => removeStopWord(word)} class="px-3 py-1 border border-red-300 text-red-600 rounded-lg text-xs hover:bg-red-50 transition-colors">Удалить</button>
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-sm text-gray-400">Список пуст — добавьте слова для фильтрации.</p>
				{/if}
			</div>

			<!-- Admin panel -->
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
				<h2 class="text-lg font-semibold text-gray-900 mb-4">Админ-панель</h2>
				{#if loadingAdmin}
					<p class="text-sm text-gray-400">Загрузка...</p>
				{:else}
					<div class="grid grid-cols-2 gap-4 mb-4">
						<div class="bg-gray-50 rounded-lg p-3">
							<p class="text-xs text-gray-500">Всего пользователей</p>
							<p class="text-xl font-bold text-gray-900">{adminStats.total_users}</p>
						</div>
						<div class="bg-gray-50 rounded-lg p-3">
							<p class="text-xs text-gray-500">Всего проектов</p>
							<p class="text-xl font-bold text-gray-900">{adminStats.total_projects}</p>
						</div>
						<div class="bg-gray-50 rounded-lg p-3">
							<p class="text-xs text-gray-500">Активных проектов</p>
							<p class="text-xl font-bold text-green-600">{adminStats.active_projects}</p>
						</div>
						<div class="bg-gray-50 rounded-lg p-3">
							<p class="text-xs text-gray-500">Баланс (₽)</p>
							<p class="text-xl font-bold text-blue-600">{adminStats.total_balance_credits}</p>
						</div>
					</div>

					<div class="bg-gray-50 rounded-lg p-3 mb-4">
						<h4 class="text-sm font-medium text-gray-700 mb-2">Очередь задач</h4>
						{#if adminStats.queue_tasks}
							<div class="space-y-1">
								{#each Object.entries(adminStats.queue_tasks) as [status, count]}
									<div class="flex justify-between text-sm">
										<span class="text-gray-600">{status}</span>
										<span class="font-medium">{count}</span>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
