<script lang="ts">
	import { api } from "$lib/api";
	import { onMount, onDestroy } from 'svelte';

	interface TimelinePoint {
		date: string;
		count: number;
	}

	interface TrackingPoint {
		position: number;
		date: string | null;
	}

	interface PositionSummary {
		best_position: number | null;
		avg_position: number | null;
		total_records: number;
	}

	let summaryLoading = $state(true);
	let summaryError = $state("");
	let stats = $state<any>(null);

	let timelineLoading = $state(true);
	let timelineData = $state<TimelinePoint[]>([]);

	let trackingLoading = $state(true);
	let trackingData = $state<TrackingPoint[]>([]);
	let trackingSummary = $state<PositionSummary | null>(null);

	// TOP ranges data
	let topRangesData = $state<any>(null);
	let topRangesLoading = $state(true);

	// Project selector for scoped analytics
	let projects = $state<any[]>([]);
	let selectedProject = $state<string>("");
	let projectLoading = $state(true);

	// Inline daily_limit edit from analytics
	let showDailyLimitModal = $state(false);
	let editingProjectName = $state("");
	let newDailyLimit = $state(0);
	let dailyLimitSaving = $state(false);
	let dailyLimitSaved = $state(false);

	// Date range for report export
	let reportFromDate = $state("");
	let reportToDate = $state("");

	function openEditDailyLimit(project: any) {
		editingProjectName = project.name;
		newDailyLimit = project.daily_limit || 500;
		showDailyLimitModal = true;
	}

	async function saveDailyLimit() {
		if (!selectedProject || newDailyLimit < 1) return;
		dailyLimitSaving = true;
		try {
			await api.projects.update(selectedProject, { daily_limit: Math.min(newDailyLimit, 100000) });
			dailyLimitSaved = true;
			await loadProjects();
			await loadSummary();
			setTimeout(() => { dailyLimitSaved = false; }, 3000);
		} catch {
			/* silent */
		} finally {
			dailyLimitSaving = false;
		}
	}

	function closeDailyLimitModal() {
		showDailyLimitModal = false;
		dailyLimitSaved = false;
	}

	let refreshInterval = $state<number | null>(null);

	async function loadProjects() {
		try {
			projects = await api.projects.list();
		} catch {
			projects = [];
		} finally {
			projectLoading = false;
		}
	}

	async function loadSummary() {
		if (selectedProject) {
			stats = await api.analytics.summary(selectedProject);
		} else {
			stats = await api.analytics.summary();
		}
	}

	async function loadTimeline() {
		if (selectedProject) {
			const data = await api.analytics.clicks(selectedProject);
			timelineData = data.timeline || [];
		} else {
			const data = await api.analytics.clicks();
			timelineData = data.timeline || [];
		}
		timelineLoading = false;
	}

	async function loadTracking() {
		if (selectedProject) {
			const data = await api.analytics.trackingPositions(selectedProject);
			trackingData = data.tracking || [];
			trackingSummary = data.summary || null;
		} else {
			trackingData = [];
			trackingSummary = null;
		}
		trackingLoading = false;
	}

	async function loadTopRanges() {
		topRangesLoading = true;
		try {
			if (selectedProject) {
				topRangesData = await api.analytics.topRanges(selectedProject);
			} else {
				topRangesData = await api.analytics.topRanges();
			}
		} catch {
			topRangesData = null;
		} finally {
			topRangesLoading = false;
		}
	}

	async function loadAll() {
		await Promise.all([
			loadSummary(),
			loadTimeline(),
			loadTracking(),
			loadTopRanges(),
		]);
	}

	onMount(async () => {
		await loadProjects();
		await Promise.all([loadSummary(), loadTimeline(), loadTracking(), loadTopRanges()]);

		refreshInterval = window.setInterval(() => {
			loadAll();
		}, 30000); // refresh every 30s
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	function handleProjectChange(e: Event) {
		const target = e.target as HTMLSelectElement;
		selectedProject = target.value;
		loadAll();
	}

	// Max count for scaling timeline chart
	const maxTimelineCount = timelineData.length > 0
		? Math.max(...timelineData.map(d => d.count))
		: 1;

	// Position colors helper
	function positionClass(pos: number): string {
		if (pos <= 3) return 'text-green-600';
		if (pos <= 10) return 'text-blue-600';
		return 'text-gray-500';
	}

	function positionLabel(pos: number): string {
		if (pos <= 3) return 'Топ-3 — Отлично!';
		if (pos <= 5) return 'Топ-5 — Хорошо';
		if (pos <= 10) return 'Первая страница';
		return 'Дальше работать';
	}

	function positionColor(pos: number): string {
		if (pos <= 3) return '#16a34a'; // green-600
		if (pos <= 5) return '#2563eb'; // blue-600
		return '#6b7280'; // gray-500
	}

	// Format date for display
	function formatDate(dateStr: string): string {
		if (!dateStr) return '';
		try {
			return new Date(dateStr).toLocaleDateString('ru-RU');
		} catch {
			return dateStr;
		}
	}

	// SVG line chart for positions
	function renderPositionChart(): string {
		if (trackingData.length < 2) return '';

		const positions = trackingData.map(d => d.position).filter(p => p > 0);
		if (positions.length < 2) return '';

		// Sort by position ascending (lower is better in search)
		const sorted = [...positions].sort((a, b) => a - b);
		const minPos = Math.min(...sorted);
		const maxPos = Math.max(...sorted);
		const range = maxPos - minPos || 1;

		const width = 600;
		const height = 200;
		const padding = { top: 20, right: 30, bottom: 30, left: 50 };
		const chartW = width - padding.left - padding.right;
		const chartH = height - padding.top - padding.bottom;

		// Scale: position on Y axis (inverted — lower is higher visually)
		// X axis: index of data point
		const points = positions.map((pos, i) => {
			const x = padding.left + (i / (positions.length - 1)) * chartW;
			const y = padding.top + ((pos - minPos) / range) * chartH;
			return `${x},${y}`;
		}).join(' ');

		// Grid lines
		let gridLines = '';
		for (let p = Math.ceil(minPos); p <= Math.floor(maxPos); p += Math.max(1, Math.floor(range / 5))) {
			const y = padding.top + ((p - minPos) / range) * chartH;
			gridLines += `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="#e5e7eb" stroke-width="1"/>`;
			gridLines += `<text x="${padding.left - 5}" y="${y + 4}" text-anchor="end" font-size="10" fill="#9ca3af">${p}</text>`;
		}

		// Area fill under line
		const areaPoints = `${padding.left},${padding.top + chartH} ${points} ${padding.left + chartW},${padding.top + chartH}`;

		return `
			<svg viewBox="0 0 ${width} ${height}" class="w-full h-64" xmlns="http://www.w3.org/2000/svg">
				${gridLines}
				<polygon points="${areaPoints}" fill="rgba(59,130,246,0.1)"/>
				<polyline points="${points}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
				${positions.map((pos, i) => {
					const x = padding.left + (i / (positions.length - 1)) * chartW;
					const y = padding.top + ((pos - minPos) / range) * chartH;
					return `<circle cx="${x}" cy="${y}" r="4" fill="${positionColor(pos)}" stroke="#fff" stroke-width="2"/>`;
				}).join('')}
			</svg>
		`;
	}

	// Download report helpers
	async function downloadReport(type: string) {
		if (!selectedProject) return;
		try {
			const fn = type === 'analytics' ? api.projects.reportAnalytics : api.projects.reportSummary;
			const url = "/api/projects/" + encodeURIComponent(selectedProject) + "/reports/" + type + ".csv";
			let fetchUrl = url;
			if (reportFromDate || reportToDate) {
				fetchUrl += "?";
				// Project service report endpoints expect 'from_date'/'to_date' (not 'start_date'/'end_date')
				if (reportFromDate) fetchUrl += "from_date=" + encodeURIComponent(reportFromDate) + "&";
				if (reportToDate) fetchUrl += "to_date=" + encodeURIComponent(reportToDate);
			}
			const blob = await fetch(fetchUrl).then(r => r.blob());
			const blobUrl = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = blobUrl;
			a.download = `report_${type}_${Date.now()}.csv`;
			a.click();
			URL.revokeObjectURL(blobUrl);
		} catch (e) {
			console.error("Export failed:", e);
		}
	}

	async function downloadTimelineReport() {
		if (!selectedProject) return;
		try {
			let timelineUrl = "/api/analytics/clicks?project_id=" + encodeURIComponent(selectedProject);
			if (reportFromDate || reportToDate) {
				if (reportFromDate) timelineUrl += "&start_date=" + encodeURIComponent(reportFromDate);
				if (reportToDate) timelineUrl += "&end_date=" + encodeURIComponent(reportToDate);
			}
			const response = await fetch(timelineUrl);
			const data = await response.json();
			let csv = 'Date,Clicks\n';
			for (const point of data.timeline || []) {
				csv += `${point.date},${point.count}\n`;
			}
			const blob = new Blob([csv], { type: 'text/csv' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = `analytics_timeline_${Date.now()}.csv`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			console.error("Export failed:", e);
		}
	}
</script>

<div class="p-6">
	<!-- Header -->
	<div class="mb-6 flex items-center justify-between">
		<div>
			<h1 class="text-2xl font-bold text-gray-900">Аналитика</h1>
			<p class="text-sm text-gray-500 mt-1">Статистика кликов, позиций и эффективности проектов</p>
		</div>

		<!-- Project selector -->
		<select
			value={selectedProject}
			onchange={handleProjectChange}
			class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white"
		>
			<option value="">Все проекты</option>
			{#each projects as project}
				<option value={project.id}>{project.name}</option>
			{/each}
		</select>
	</div>

	{#if summaryError}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{summaryError}</div>
	{/if}

	<!-- Stats cards -->
	<div class="grid grid-cols-4 gap-6 mb-8">
		<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
			<p class="text-sm text-gray-500">Всего кликов</p>
			<p class="text-3xl font-bold text-gray-900 mt-1">{stats?.total_clicks?.toLocaleString() ?? '—'}</p>
		</div>
		<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
			<p class="text-sm text-gray-500">Успешность</p>
			<p class="text-3xl font-bold text-green-600 mt-1">
				{stats && stats.completed_rate ? (stats.completed_rate * 100).toFixed(1) + '%' : '—'}
			</p>
		</div>
		<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
			<p class="text-sm text-gray-500">Средняя позиция</p>
			<p class="text-3xl font-bold text-blue-600 mt-1">{stats?.avg_position ?? '—'}</p>
		</div>
		<div class="bg-white border border-gray-200 rounded-xl p-5 shadow-sm relative group">
			<p class="text-sm text-gray-500">Активных проектов</p>
			<p class="text-3xl font-bold text-gray-900 mt-1">{projects.length}</p>
			{#if selectedProject}
				<button onclick={() => { const p = projects.find(x => x.id === selectedProject); if (p) openEditDailyLimit(p); }} class="absolute top-4 right-4 text-xs text-blue-600 hover:text-blue-800 opacity-0 group-hover:opacity-100 transition-opacity" title="Редактировать лимит кликов">
					✏️ Лимит
				</button>
			{/if}
		</div>
	</div>

	<!-- Timeline chart -->
	<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
		<h3 class="font-medium text-gray-900 mb-4">Клики по дням</h3>

		{#if timelineLoading}
			<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">Загрузка...</div>
		{:else if timelineData.length === 0}
			<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
				Нет данных о кликах. Клики начнут отображаться после выполнения первых задач.
			</div>
		{:else}
			<!-- Bar chart using CSS -->
			<div class="flex items-end gap-1 h-64 px-2">
				{#each timelineData as point, i}
					<div class="flex-1 flex flex-col items-center justify-end group relative">
						<!-- Tooltip -->
						<div class="absolute bottom-full mb-2 hidden group-hover:block bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap z-10">
							{formatDate(point.date)}: {point.count} кликов
						</div>
						<!-- Bar -->
						<div
							class="w-full bg-blue-500 hover:bg-blue-600 rounded-t transition-colors cursor-pointer"
							style="height: calc(({point.count} / {maxTimelineCount}) * 100%)"
						></div>
					</div>
				{/each}
			</div>
			<!-- Date labels (last few) -->
			<div class="flex justify-between mt-2 text-xs text-gray-400 px-2">
				<span>{formatDate(timelineData[0]?.date)}</span>
				<span>{formatDate(timelineData[timelineData.length - 1]?.date)}</span>
			</div>
		{/if}
	</div>

	<!-- TOP ranges chart -->
	<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
		<h3 class="font-medium text-gray-900 mb-4">Клики по диапазону позиций</h3>

		{#if topRangesLoading}
			<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">Загрузка...</div>
		{:else if topRangesData && topRangesData.ranges.length > 0}
			<div class="grid grid-cols-6 gap-3 mb-4">
				{#each topRangesData.ranges as range}
					<div class="bg-gray-50 rounded-lg p-3 text-center">
						<p class="text-xs text-gray-500 mb-1">{range.label}</p>
						<p class="text-xl font-bold text-gray-900">{range.clicks}</p>
						{#if range.avg_position}
							<p class="text-xs text-blue-600 mt-1">ср: #{range.avg_position}</p>
						{/if}
					</div>
				{/each}
			</div>
			<!-- Horizontal bar chart -->
			<div class="space-y-2">
				{#each topRangesData.ranges as range}
					<div class="flex items-center gap-3">
						<span class="text-xs text-gray-500 w-24 text-right shrink-0">{range.label}</span>
						<div class="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden relative">
							<div
								class="h-full rounded-full transition-all"
								style="width: calc({range.clicks} / {topRangesData.total_clicks || 1} * 100%); background: {range.label.includes('Топ') ? '#16a34a' : range.label.includes('4–5') ? '#2563eb' : range.label.includes('6–10') ? '#3b82f6' : range.label.includes('11–20') ? '#8b5cf6' : range.label.includes('21–50') ? '#f59e0b' : '#6b7280'};"
							></div>
							<span class="absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-700">
								{range.clicks} ({topRangesData.total_clicks > 0 ? ((range.clicks / topRangesData.total_clicks) * 100).toFixed(1) : 0}%)
							</span>
						</div>
					</div>
				{/each}
			</div>
			{#if topRangesData.overall_avg_position}
				<div class="mt-4 pt-3 border-t border-gray-200 text-sm text-gray-500">
					Общая средняя позиция по всем кликам: <span class="font-bold text-blue-600">#{topRangesData.overall_avg_position}</span>
				</div>
			{/if}
		{:else}
			<div class="h-32 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400 text-sm">
				Нет данных о позициях. Данные появятся после выполнения задач с зафиксированными позициями.
			</div>
		{/if}
	</div>

	<!-- Position tracking chart -->
	<div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm mb-6">
		<h3 class="font-medium text-gray-900 mb-4">Отслеживание позиций</h3>

		{#if trackingSummary}
			<!-- Summary badges -->
			<div class="flex gap-4 mb-4">
				<div class="px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
					<span class="text-xs text-green-700">Лучшая:</span>
					<span class="text-sm font-bold text-green-900 ml-1">#{trackingSummary.best_position}</span>
				</div>
				<div class="px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg">
					<span class="text-xs text-blue-700">Средняя:</span>
					<span class="text-sm font-bold text-blue-900 ml-1">{trackingSummary.avg_position}</span>
				</div>
				<div class="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
					<span class="text-xs text-gray-700">Записей:</span>
					<span class="text-sm font-bold text-gray-900 ml-1">{trackingSummary.total_records}</span>
				</div>
			</div>
		{/if}

		{#if trackingLoading}
			<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">Загрузка...</div>
		{:else if selectedProject && trackingData.length > 0}
			<!-- SVG Line chart -->
			<div class="overflow-x-auto">
				{@html renderPositionChart()}
			</div>
		{:else}
			<div class="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
				Выберите проект для просмотра отслеживания позиций.
			</div>
		{/if}
	</div>

	<!-- Position history table (for selected project) -->
	{#if selectedProject && trackingData.length > 0}
		<div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm mb-6">
			<div class="px-6 py-4 border-b border-gray-200">
				<h3 class="font-medium text-gray-900">История позиций</h3>
			</div>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 border-b border-gray-200">
						<tr>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Позиция</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Дата регистрации</th>
							<th class="px-4 py-3 text-left font-medium text-gray-600">Оценка</th>
						</tr>
					</thead>
					<tbody>
						{#each trackingData.slice(-50).reverse() as point}
							<tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
								<td class="px-4 py-3">
									<span class="font-mono font-bold {positionClass(point.position)}">#{point.position}</span>
								</td>
								<td class="px-4 py-3 text-gray-500">{point.date ? formatDate(point.date) : '—'}</td>
								<td class="px-4 py-3">
									<span class="inline-flex px-2 py-1 rounded-full text-xs font-medium {
										point.position <= 3 ? 'bg-green-100 text-green-800' :
										point.position <= 10 ? 'bg-blue-100 text-blue-800' :
										'bg-gray-100 text-gray-800'
									}">
										{positionLabel(point.position)}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- Date range selector for export -->
	{#if selectedProject}
		<div class="bg-white border border-gray-200 rounded-xl p-6 mb-6">
			<h3 class="font-medium text-gray-900 mb-4">Экспорт отчёта</h3>
			<div class="flex flex-wrap items-end gap-4">
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Период с</label>
					<input type="date" bind:value={reportFromDate} class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				</div>
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Период по</label>
					<input type="date" bind:value={reportToDate} class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
				</div>
				{#if reportFromDate || reportToDate}
					<button onclick={() => { reportFromDate = ""; reportToDate = ""; }} class="px-3 py-2 text-sm text-gray-500 hover:text-gray-700 transition-colors">Очистить</button>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Export buttons -->
	<div class="flex gap-3 flex-wrap">
		<button
			class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
			onclick={async () => { downloadReport('analytics'); }}>
			Аналитика по запросам (CSV)
		</button>
		<button
			class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
			onclick={async () => { downloadReport('summary'); }}>
			Сводный отчёт (CSV)
		</button>
		<button
			class="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium transition-colors"
			onclick={async () => { downloadTimelineReport(); }}>
			График кликов (CSV)
		</button>
	</div>

	<!-- Daily limit edit modal -->
	{#if showDailyLimitModal}
		<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onmousedown={(e) => e.target === e.currentTarget && closeDailyLimitModal()}>
			<div class="bg-white rounded-xl shadow-2xl w-full max-w-md p-6 m-4">
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-lg font-semibold text-gray-900">Редактировать лимит кликов</h2>
					<button onclick={closeDailyLimitModal} class="text-gray-400 hover:text-gray-600">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
					</button>
				</div>

				{#if dailyLimitSaved}
					<div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">Лимит успешно обновлён</div>
				{/if}

				<div class="space-y-4">
					<div class="p-3 bg-gray-50 rounded-lg">
						<p class="text-sm font-medium text-gray-900">{editingProjectName}</p>
						<p class="text-xs text-gray-500 mt-1">Текущий лимит: <span class="font-bold">{newDailyLimit} кликов/день</span></p>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">Новый ежедневный лимит</label>
						<input type="number" bind:value={newDailyLimit} min="1" max="100000" step="1" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
						<p class="text-xs text-gray-400 mt-1">Максимум: 100 000 кликов/день</p>
					</div>

					<!-- Quick presets -->
					<div>
						<p class="text-xs text-gray-500 mb-2">Быстрый выбор:</p>
						<div class="flex flex-wrap gap-2">
							{#each [10, 50, 100, 200, 500, 1000, 5000] as preset}
								<button onclick={() => newDailyLimit = preset} class="px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 transition-colors">{preset}</button>
							{/each}
						</div>
					</div>
				</div>

				<div class="flex justify-end gap-3 mt-6">
					<button onclick={closeDailyLimitModal} class="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition-colors">Отмена</button>
					<button onclick={saveDailyLimit} disabled={dailyLimitSaving || newDailyLimit < 1} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white rounded-lg text-sm font-medium transition-colors">
						{dailyLimitSaving ? 'Сохранение…' : 'Применить лимит'}
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
