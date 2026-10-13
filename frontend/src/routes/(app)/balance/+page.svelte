<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from 'svelte';

	let projects = $state<any[]>([]);
	let selectedProjectId = $state("");
	let balanceAmount = $state("");
	let balanceDescription = $state("");
	let loading = $state(true);
	let addingBalance = $state(false);
	let error = $state("");
	let successMsg = $state("");

	interface TxEntry {
		id: string;
		amount_kopeks: number;
		amount_rub: number;
		type: string;
		description: string;
		created_at: string | null;
	}

	let transactions = $state<TxEntry[]>([]);
	let txTotal = $state(0);
	let currentPage = $state(1);
	const pageSize = 20;
	let totalPages = $state(1);
	let projectBalance = $state(0);
	let totalBalance = $state(0);

	async function loadProjects() {
		try {
			const data = await api.projects.list();
			projects = data.items || [];
			if (projects.length > 0) {
				selectedProjectId = projects[0].id;
				loadProjectBalance(selectedProjectId);
			}
			totalBalance = projects.reduce((sum: number, p: any) => sum + (p.balance_rub || p.balance_credits / 100 || 0), 0);
			await loadTransactions();
		} catch {
			error = "Ошибка загрузки проектов";
		} finally {
			loading = false;
		}
	}

	async function loadProjectBalance(pid: string) {
		try {
			const data = await api.balance.get(pid);
			projectBalance = data.balance_rub || 0;
		} catch {}
	}

	async function loadTransactions() {
		try {
			if (!selectedProjectId) return;
			const data = await api.balance.history(selectedProjectId, currentPage, pageSize);
			transactions = data.transactions || [];
			txTotal = data.total || 0;
			totalPages = data.total_pages || 1;
			loadProjectBalance(selectedProjectId);
		} catch {}
	}

	async function addBalanceToProject() {
		if (!selectedProjectId || !balanceAmount) return;
		const amount = parseFloat(balanceAmount);
		if (isNaN(amount) || amount <= 0) {
			error = "Введите корректную сумму";
			return;
		}

		addingBalance = true;
		error = "";
		successMsg = "";

		try {
			const res = await api.balance.add(selectedProjectId, {
				amount: amount,
				description: balanceDescription || "Пополнение вручную",
			});

			const project = projects.find((p: any) => p.id === selectedProjectId);
			if (project) {
				project.balance_credits = res.balance;
				project.balance_rub = res.balance_rub;
			}
			totalBalance += amount;

			balanceAmount = "";
			balanceDescription = "";
			successMsg = `${amount} ₽ добавлено`;
			setTimeout(() => { successMsg = ""; }, 4000);

			await loadTransactions();
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка пополнения";
		}
		addingBalance = false;
	}

	function typeLabel(type: string): string {
		const labels: Record<string, string> = { add: 'Пополнение', set: 'Установка баланса', spend: 'Расход', refund: 'Возврат' };
		return labels[type] || type;
	}

	onMount(() => { loadProjects(); });
</script>

<div class="p-6">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">Баланс</h1>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}
	{#if successMsg}
		<div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">{successMsg}</div>
	{/if}

	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else}

	<!-- Summary cards -->
	<div class="grid grid-cols-3 gap-4 mb-6">
		<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
			<p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Общий баланс</p>
			<p class="text-2xl font-bold text-green-600">{totalBalance.toFixed(2)} ₽</p>
		</div>
		<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
			<p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Проектов</p>
			<p class="text-2xl font-bold text-gray-900">{projects.length}</p>
		</div>
		<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
			<p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Операций</p>
			<p class="text-2xl font-bold text-gray-900">{txTotal}</p>
		</div>
	</div>

	<!-- Add balance form -->
	<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
		<h2 class="text-lg font-semibold text-gray-900 mb-4">Пополнить баланс проекта</h2>
		<form onsubmit={(e) => { e.preventDefault(); addBalanceToProject(); }} class="space-y-4">
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1">Проект</label>
				<select bind:value={selectedProjectId} class="w-full max-w-md px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
					{#if projects.length === 0}
						<option value="">Нет проектов</option>
					{:else}
						{#each projects as p}
							<option value={p.id}>{p.name} ({p.domain || 'без домена'}) — {(p.balance_rub || p.balance_credits / 100 || 0).toFixed(2)} ₽</option>
						{/each}
					{/if}
				</select>
			</div>

			<div class="flex gap-3 items-end">
				<div class="flex-1 max-w-xs">
					<label class="block text-sm font-medium text-gray-700 mb-1">Сумма (₽)</label>
					<input type="number" bind:value={balanceAmount} min="1" step="0.01" placeholder="100" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
				</div>
				<button type="submit" disabled={addingBalance} class="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-300 text-white rounded-lg text-sm font-medium transition-colors whitespace-nowrap">
					{addingBalance ? 'Добавление…' : 'Добавить баланс'}
				</button>
			</div>

			<div class="max-w-md">
				<label class="block text-sm font-medium text-gray-700 mb-1">Описание (опционально)</label>
				<input type="text" bind:value={balanceDescription} placeholder="Пополнение с карты..." class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
			</div>
		</form>
	</div>

	<!-- Transaction history -->
	<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
		<h2 class="text-lg font-semibold text-gray-900 mb-4">История транзакций</h2>

		{#if transactions.length === 0}
			<div class="text-center py-12">
				<svg class="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z"/>
				</svg>
				<p class="text-sm text-gray-400">История транзакций пуста для этого проекта</p>
				<p class="text-xs text-gray-300 mt-1">Пополните баланс, чтобы появились записи</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each transactions as tx}
					<div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
						<div class="flex items-center gap-3">
							<span class={`w-2 h-2 rounded-full ${tx.type === 'add' ? 'bg-green-500' : tx.type === 'set' ? 'bg-blue-500' : tx.type === 'spend' ? 'bg-red-500' : 'bg-yellow-500'}`}></span>
							<div>
								<p class="text-sm font-medium text-gray-900">{typeLabel(tx.type)}</p>
								{#if tx.description}
									<p class="text-xs text-gray-500">{tx.description}</p>
								{/if}
							</div>
						</div>
						<div class="text-right">
							<p class="text-sm font-medium {tx.amount_kopeks > 0 ? 'text-green-600' : 'text-red-600'}">
								{tx.amount_kopeks > 0 ? '+' : ''}{tx.amount_rub.toFixed(2)} ₽
							</p>
							<p class="text-xs text-gray-400">{tx.created_at ? new Date(tx.created_at).toLocaleString('ru-RU') : ''}</p>
						</div>
					</div>
				{/each}
			</div>

			<!-- Pagination -->
			{#if totalPages > 1}
				<div class="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
					<p class="text-sm text-gray-500">Страница {currentPage} из {totalPages} ({txTotal} операций)</p>
					<div class="flex gap-1">
						<button onclick={() => { if (currentPage > 1) currentPage--; loadTransactions(); }} disabled={currentPage <= 1} class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
							Назад
						</button>
						<button onclick={() => { if (currentPage < totalPages) currentPage++; loadTransactions(); }} disabled={currentPage >= totalPages} class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
							Вперёд
						</button>
					</div>
				</div>
			{/if}
		{/if}
	</div>

	{/if}
</div>
