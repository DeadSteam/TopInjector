<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from "svelte";

	interface Plan {
		id: string;
		slug: string;
		display_name: string;
		price_per_day: number;
		price_per_month: number;
		max_users: number;
		max_projects: number;
	}

	let plans = $state<Plan[]>([]);
	let currentSlug = $state("");
	let limits = $state<{ max_users: number; max_projects: number }>({ max_users: 0, max_projects: 0 });
	let usage = $state<{ projects: number }>({ projects: 0 });
	let loading = $state(true);
	let error = $state("");
	let successMsg = $state("");
	let switching = $state("");

	const rub = (kop: number) => (kop / 100).toLocaleString("ru-RU");

	async function load() {
		loading = true;
		error = "";
		try {
			const [list, status] = await Promise.all([api.plans.list(), api.plans.status()]);
			plans = list.plans || [];
			currentSlug = status.plan?.slug || "";
			limits = status.limits || limits;
			usage = status.usage || usage;
		} catch {
			error = "Не удалось загрузить тарифы";
		} finally {
			loading = false;
		}
	}

	async function switchTo(slug: string) {
		if (slug === currentSlug) return;
		switching = slug;
		error = "";
		successMsg = "";
		try {
			await api.plans.switch(slug);
			successMsg = "Тариф изменён";
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : "Не удалось сменить тариф";
		} finally {
			switching = "";
		}
	}

	onMount(load);
</script>

<div class="p-6">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Тариф</h1>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}
	{#if successMsg}
		<div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">{successMsg}</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}
		<!-- Current plan + usage -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
				<p class="text-sm text-gray-500 mb-1">Текущий тариф</p>
				<p class="text-xl font-bold text-gray-900">{plans.find(p => p.slug === currentSlug)?.display_name || currentSlug || "—"}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
				<p class="text-sm text-gray-500 mb-1">Проекты</p>
				<p class="text-xl font-bold text-gray-900">{usage.projects} / {limits.max_projects}</p>
			</div>
			<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
				<p class="text-sm text-gray-500 mb-1">Пользователи (лимит)</p>
				<p class="text-xl font-bold text-gray-900">{limits.max_users}</p>
			</div>
		</div>

		<!-- Plan catalogue -->
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each plans as plan (plan.id)}
				<div class="bg-white border rounded-xl shadow-sm p-6 flex flex-col {plan.slug === currentSlug ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-200'}">
					<div class="flex items-center justify-between mb-2">
						<h2 class="text-lg font-semibold text-gray-900">{plan.display_name}</h2>
						{#if plan.slug === currentSlug}
							<span class="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">Активен</span>
						{/if}
					</div>
					<p class="text-2xl font-bold text-gray-900 mb-1">
						{plan.price_per_day === 0 ? "Бесплатно" : `${rub(plan.price_per_day)} ₽`}
						{#if plan.price_per_day > 0}<span class="text-sm font-normal text-gray-400">/день</span>{/if}
					</p>
					{#if plan.price_per_month > 0}
						<p class="text-sm text-gray-500 mb-4">{rub(plan.price_per_month)} ₽ / месяц</p>
					{:else}
						<p class="text-sm text-gray-500 mb-4">&nbsp;</p>
					{/if}
					<ul class="text-sm text-gray-600 space-y-1 mb-6">
						<li>До {plan.max_projects} проектов</li>
						<li>До {plan.max_users} пользователей</li>
					</ul>
					<button
						onclick={() => switchTo(plan.slug)}
						disabled={plan.slug === currentSlug || switching === plan.slug}
						class="mt-auto px-4 py-2 rounded-lg text-sm font-medium transition-colors {plan.slug === currentSlug ? 'bg-gray-100 text-gray-400 cursor-default' : 'bg-blue-600 hover:bg-blue-700 text-white'}"
					>
						{plan.slug === currentSlug ? "Текущий" : switching === plan.slug ? "..." : "Перейти"}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
