<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from "svelte";

	interface WhiteLabel {
		domain: string | null;
		dns_status: string;
		platform_name: string;
		accent_color: string;
		description_md: string;
		welcome_text_md: string;
		website_url: string | null;
		logo_light_key: string | null;
		logo_dark_key: string | null;
		favicon_key: string | null;
		is_active: boolean;
	}

	let wl = $state<WhiteLabel | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let checkingDns = $state(false);
	let error = $state("");
	let successMsg = $state("");

	const MAX_BLURB = 700;
	const dnsLabel: Record<string, string> = { pending: "ожидает проверки", verified: "подтверждён", error: "ошибка" };
	const dnsClass: Record<string, string> = { pending: "text-gray-500", verified: "text-green-600", error: "text-red-600" };

	async function load() {
		loading = true;
		error = "";
		try {
			wl = await api.whitelabel.get();
		} catch {
			error = "Не удалось загрузить настройки";
		} finally {
			loading = false;
		}
	}

	async function save() {
		if (!wl) return;
		if (wl.description_md.length > MAX_BLURB || wl.welcome_text_md.length > MAX_BLURB) {
			error = `Описание и приветствие — не более ${MAX_BLURB} символов`;
			return;
		}
		saving = true;
		error = "";
		successMsg = "";
		try {
			wl = await api.whitelabel.update({
				domain: wl.domain,
				platform_name: wl.platform_name,
				accent_color: wl.accent_color,
				description_md: wl.description_md,
				welcome_text_md: wl.welcome_text_md,
				website_url: wl.website_url,
				logo_light_key: wl.logo_light_key,
				logo_dark_key: wl.logo_dark_key,
				favicon_key: wl.favicon_key,
				is_active: wl.is_active,
			});
			successMsg = "Сохранено";
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка сохранения";
		} finally {
			saving = false;
		}
	}

	async function checkDns() {
		checkingDns = true;
		error = "";
		try {
			const res = await api.whitelabel.checkDns();
			if (wl) wl.dns_status = res.dns_status;
		} catch (e) {
			error = e instanceof Error ? e.message : "Не удалось проверить домен";
		} finally {
			checkingDns = false;
		}
	}

	onMount(load);
</script>

<div class="p-6">
	<h1 class="text-2xl font-bold text-gray-900 mb-1">Брендинг (White Label)</h1>
	<p class="text-sm text-gray-500 mb-6">Название, цвет, логотипы и собственный домен панели.</p>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}
	{#if successMsg}
		<div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">{successMsg}</div>
	{/if}

	{#if loading || !wl}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}
		<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6 max-w-2xl space-y-5">
			<div>
				<label for="pname" class="block text-sm text-gray-600 mb-1">Название платформы</label>
				<input id="pname" bind:value={wl.platform_name} class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
			</div>

			<div>
				<label for="accent" class="block text-sm text-gray-600 mb-1">Акцентный цвет</label>
				<div class="flex items-center gap-3">
					<input id="accent" type="color" bind:value={wl.accent_color} class="h-9 w-12 border border-gray-300 rounded cursor-pointer" />
					<input bind:value={wl.accent_color} class="w-32 px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
				</div>
			</div>

			<div>
				<label for="website" class="block text-sm text-gray-600 mb-1">Сайт</label>
				<input id="website" bind:value={wl.website_url} placeholder="https://example.com" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
			</div>

			<div>
				<label for="desc" class="block text-sm text-gray-600 mb-1">Описание <span class="text-gray-400">({wl.description_md.length}/{MAX_BLURB})</span></label>
				<textarea id="desc" bind:value={wl.description_md} rows="3" maxlength={MAX_BLURB} class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"></textarea>
			</div>

			<div>
				<label for="welcome" class="block text-sm text-gray-600 mb-1">Приветственный текст <span class="text-gray-400">({wl.welcome_text_md.length}/{MAX_BLURB})</span></label>
				<textarea id="welcome" bind:value={wl.welcome_text_md} rows="3" maxlength={MAX_BLURB} class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"></textarea>
			</div>

			<div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
				<div>
					<label for="logo-light" class="block text-sm text-gray-600 mb-1">Логотип (светлый)</label>
					<input id="logo-light" bind:value={wl.logo_light_key} placeholder="URL / ключ" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				</div>
				<div>
					<label for="logo-dark" class="block text-sm text-gray-600 mb-1">Логотип (тёмный)</label>
					<input id="logo-dark" bind:value={wl.logo_dark_key} placeholder="URL / ключ" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				</div>
				<div>
					<label for="favicon" class="block text-sm text-gray-600 mb-1">Favicon</label>
					<input id="favicon" bind:value={wl.favicon_key} placeholder="URL / ключ" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				</div>
			</div>

			<div class="border-t border-gray-100 pt-5">
				<label for="domain" class="block text-sm text-gray-600 mb-1">Свой домен</label>
				<div class="flex flex-wrap items-center gap-3">
					<input id="domain" bind:value={wl.domain} placeholder="panel.example.com" class="flex-1 min-w-[220px] px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
					<span class="text-sm {dnsClass[wl.dns_status] || 'text-gray-500'}">DNS: {dnsLabel[wl.dns_status] || wl.dns_status}</span>
					<button onclick={checkDns} disabled={checkingDns || !wl.domain} class="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors">
						{checkingDns ? "..." : "Проверить DNS"}
					</button>
				</div>
				<p class="text-xs text-gray-400 mt-1">Смена домена сбрасывает статус до «ожидает проверки» — сохраните, затем проверьте DNS.</p>
			</div>

			<label class="flex items-center gap-2 text-sm text-gray-700">
				<input type="checkbox" bind:checked={wl.is_active} class="rounded border-gray-300" />
				Брендинг активен
			</label>

			<div class="pt-2">
				<button onclick={save} disabled={saving} class="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
					{saving ? "Сохранение..." : "Сохранить"}
				</button>
			</div>
		</div>
	{/if}
</div>
