<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from "svelte";

	interface Account {
		id: string;
		service_type: string;
		display_name: string;
		config_json: Record<string, unknown>;
		is_active: boolean;
	}

	const SERVICE_TYPES = [
		{ value: "yandex_webmaster", label: "Яндекс Вебмастер" },
		{ value: "xmlriver", label: "XMLRiver" },
		{ value: "xmlstock", label: "XMLStock" },
	];
	const typeLabel = (t: string) => SERVICE_TYPES.find(s => s.value === t)?.label || t;

	let accounts = $state<Account[]>([]);
	let loading = $state(true);
	let error = $state("");

	// new-account form
	let newType = $state("yandex_webmaster");
	let newName = $state("");
	let creating = $state(false);

	// per-account domains (yandex webmaster)
	let openDomainsFor = $state<string | null>(null);
	let domains = $state<{ id: string; domain: string; is_confirmed: boolean }[]>([]);
	let newDomain = $state("");

	async function load() {
		loading = true;
		error = "";
		try {
			accounts = (await api.externalServices.list()).accounts || [];
		} catch {
			error = "Не удалось загрузить аккаунты";
		} finally {
			loading = false;
		}
	}

	async function create() {
		if (!newName.trim()) { error = "Укажите название"; return; }
		creating = true;
		error = "";
		try {
			await api.externalServices.create({ service_type: newType, display_name: newName.trim() });
			newName = "";
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка создания";
		} finally {
			creating = false;
		}
	}

	async function remove(id: string) {
		if (!confirm("Удалить этот аккаунт?")) return;
		try {
			await api.externalServices.delete(id);
			if (openDomainsFor === id) openDomainsFor = null;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка удаления";
		}
	}

	async function toggleDomains(id: string) {
		if (openDomainsFor === id) { openDomainsFor = null; return; }
		openDomainsFor = id;
		domains = [];
		newDomain = "";
		try {
			domains = (await api.externalServices.domains(id)).domains || [];
		} catch {
			error = "Не удалось загрузить домены";
		}
	}

	async function addDomain(id: string) {
		if (!newDomain.trim()) return;
		try {
			await api.externalServices.addDomain(id, newDomain.trim());
			newDomain = "";
			domains = (await api.externalServices.domains(id)).domains || [];
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка добавления домена";
		}
	}

	onMount(load);
</script>

<div class="p-6">
	<h1 class="text-2xl font-bold text-gray-900 mb-1">Внешние сервисы</h1>
	<p class="text-sm text-gray-500 mb-6">Подключение Яндекс Вебмастера и сервисов проверки позиций (XMLRiver, XMLStock).</p>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	<!-- Add account -->
	<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
		<h2 class="text-lg font-semibold text-gray-900 mb-4">Добавить аккаунт</h2>
		<div class="flex flex-wrap gap-3 items-end">
			<div>
				<label for="svc-type" class="block text-sm text-gray-600 mb-1">Сервис</label>
				<select id="svc-type" bind:value={newType} class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
					{#each SERVICE_TYPES as s (s.value)}<option value={s.value}>{s.label}</option>{/each}
				</select>
			</div>
			<div class="flex-1 min-w-[200px]">
				<label for="svc-name" class="block text-sm text-gray-600 mb-1">Название</label>
				<input id="svc-name" bind:value={newName} placeholder="Мой аккаунт" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
			</div>
			<button onclick={create} disabled={creating} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
				{creating ? "..." : "Добавить"}
			</button>
		</div>
	</div>

	<!-- Accounts list -->
	<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
		<h2 class="text-lg font-semibold text-gray-900 mb-4">Подключённые аккаунты</h2>
		{#if loading}
			<div class="text-center py-12 text-gray-400">Загрузка...</div>
		{:else if accounts.length === 0}
			<div class="text-center py-12 text-gray-400">Пока нет подключённых аккаунтов</div>
		{:else}
			<div class="space-y-3">
				{#each accounts as acc (acc.id)}
					<div class="border border-gray-200 rounded-lg p-4">
						<div class="flex items-center justify-between">
							<div>
								<p class="font-medium text-gray-900">{acc.display_name}</p>
								<p class="text-xs text-gray-500">{typeLabel(acc.service_type)}</p>
							</div>
							<div class="flex gap-2">
								{#if acc.service_type === "yandex_webmaster"}
									<button onclick={() => toggleDomains(acc.id)} class="px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
										{openDomainsFor === acc.id ? "Скрыть домены" : "Домены"}
									</button>
								{/if}
								<button onclick={() => remove(acc.id)} class="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">Удалить</button>
							</div>
						</div>

						{#if openDomainsFor === acc.id}
							<div class="mt-4 pt-4 border-t border-gray-100">
								<div class="flex gap-2 mb-3">
									<input bind:value={newDomain} placeholder="example.com" class="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
									<button onclick={() => addDomain(acc.id)} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition-colors">Добавить</button>
								</div>
								{#if domains.length === 0}
									<p class="text-sm text-gray-400">Нет добавленных доменов</p>
								{:else}
									<ul class="space-y-1">
										{#each domains as d (d.id)}
											<li class="flex items-center justify-between text-sm">
												<span class="text-gray-700">{d.domain}</span>
												<span class="text-xs {d.is_confirmed ? 'text-green-600' : 'text-gray-400'}">{d.is_confirmed ? "подтверждён" : "не подтверждён"}</span>
											</li>
										{/each}
									</ul>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
