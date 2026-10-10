<script lang="ts">
	import { onMount } from 'svelte';

	onMount(() => {
		// Load Redocly standalone and render OpenAPI spec
		const script = document.createElement('script');
		script.src = 'https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.js';
		script.onload = () => {
			if (typeof Redoc !== 'undefined') {
				const el = document.getElementById('redoc-container');
				if (el) {
					// Fetch the spec from our gateway
					const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
					fetch(`${BASE_URL}/api/internal/openapi.json`)
						.then(r => r.json())
						.then(spec => {
							Redoc.init(spec, {
								showExtensions: true,
								sortPropsAlphabetically: true,
							theme: {
									rightPanelBackgroundColor: '#1e293b',
									sizes: {
										baseFontSize: '14px',
									},
								},
							}, el);
						})
						.catch(() => {
							// Fallback if no spec endpoint exists
							const fallback = document.getElementById('fallback-docs');
							if (fallback) fallback.style.display = 'block';
						});
			}
		};
		document.head.appendChild(script);
	});
</script>

<div class="p-6 max-w-[1600px]">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">API Документация</h1>

	<p class="text-sm text-gray-500 mb-4">Интерактивная документация API TopInjector. Для корректной работы необходим доступ к Gateway (порт 8080).</p>

	<!-- Redoc container -->
	<div id="redoc-container" class="bg-white border border-gray-200 rounded-xl shadow-sm min-h-[600px]" />

	<!-- Fallback documentation when spec endpoint unavailable -->
	<div id="fallback-docs" class="hidden space-y-6">
		<section class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
			<h2 class="text-xl font-semibold text-gray-900 mb-4">External API — /api/external/v1/</h2>
			<p class="text-sm text-gray-600 mb-4">Все внешние запросы используют заголовок <code class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">X-Auth-Token</code> с project token.</p>

			<div class="space-y-3">
				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/projects</span>
					</div>
					<p class="text-sm text-gray-600">Создание проекта. Тело: <code class="text-xs">{ name, domain, region, schedule_type }</code></p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-bold">PUT</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/projects/{id}</span>
					</div>
					<p class="text-sm text-gray-600">Обновление проекта.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/terms/upsert</span>
					</div>
					<p class="text-sm text-gray-600">Массовое добавление/обновление ключевых запросов. Тело: array of { text, url, click_url, geo, daily_count }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/queue/push</span>
					</div>
					<p class="text-sm text-gray-600">Добавление задач в очередь. Тело: { project_id, tasks: [...] }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/queue/results</span>
					</div>
					<p class="text-sm text-gray-600">Отправка результатов взаимодействия. Тело: { project_id, results: [...] }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-pink-100 text-pink-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/users</span>
					</div>
					<p class="text-sm text-gray-600">Пригласить пользователя в организацию. Тело: { email, role }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/balance/add</span>
					</div>
					<p class="text-sm text-gray-600">Пополнить баланс проекта. Тело: { project_id, amount }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/balance/set</span>
					</div>
					<p class="text-sm text-gray-600">Установить баланс проекта. Тело: { project_id, amount }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-bold">GET</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/health</span>
					</div>
					<p class="text-sm text-gray-600">Проверка доступности API. Возвращает { status: "ok" }.</p>
				</div>
			</div>
		</section>

		<section class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
			<h2 class="text-xl font-semibold text-gray-900 mb-4">Внутренний API (Auth + Users)</h2>
			<p class="text-sm text-gray-600 mb-4">Аутентификация: <code class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">Authorization: Bearer &lt;jwt_token&gt;</code></p>

			<div class="space-y-3">
				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/auth/login</span>
					</div>
					<p class="text-sm text-gray-600">Вход. Тело: { email, password }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/auth/register</span>
					</div>
					<p class="text-sm text-gray-600">Регистрация. Тело: { email, password, display_name }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/auth/refresh</span>
					</div>
					<p class="text-sm text-gray-600">Обновление токена. Тело: { refresh_token }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-bold">GET</span>
						<span class="font-mono text-sm text-gray-900">/api/users/profile</span>
					</div>
					<p class="text-sm text-gray-600">Профиль пользователя.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-bold">PUT</span>
						<span class="font-mono text-sm text-gray-900">/api/users/profile</span>
					</div>
					<p class="text-sm text-gray-600">Обновить профиль. Тело: { display_name }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-bold">GET</span>
						<span class="font-mono text-sm text-gray-900">/api/users/api-tokens</span>
					</div>
					<p class="text-sm text-gray-600">Список API токенов.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/users/api-tokens</span>
					</div>
					<p class="text-sm text-gray-600">Создать новый API токен.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/users/settings/messenger</span>
					</div>
					<p class="text-sm text-gray-600">Настройки мессенджеров (Telegram webhook URL).</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-bold">GET</span>
						<span class="font-mono text-sm text-gray-900">/api/users/settings/messenger</span>
					</div>
					<p class="text-sm text-gray-600">Получить текущие настройки мессенджеров.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/users/settings/external-services</span>
					</div>
					<p class="text-sm text-gray-600">Настройки внешних сервисов (XML River, XMLStock).</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">GET</span>
						<span class="font-mono text-sm text-gray-900">/api/users/settings/external-services</span>
					</div>
					<p class="text-sm text-gray-600">Получить текущие настройки внешних сервисов.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/users/password</span>
					</div>
					<p class="text-sm text-gray-600">Сменить пароль. Тело: { current_password, new_password }.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-cyan-100 text-cyan-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/projects/{id}/queries/bulk-update</span>
					</div>
					<p class="text-sm text-gray-600">Массовое обновление запросов. Тело: { query_ids, daily_clicks?, geo?

, click_url? }.</p>
				</div>
			</div>
		</section>

		<section class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
			<h2 class="text-xl font-semibold text-gray-900 mb-4">Модель данных</h2>
			<div class="space-y-3 text-sm">
				<div class="bg-gray-50 rounded-lg p-4">
					<p class="font-medium text-gray-900 mb-1">User</p>
					<p class="text-gray-600">id, email, display_name, is_active, plan, balance</p>
				</div>
				<div class="bg-gray-50 rounded-lg p-4">
					<p class="font-medium text-gray-900 mb-1">Project</p>
					<p class="text-gray-600">id, name, domain, region, strategy_type (daily/monthly/hourly), daily_limit, is_active, integrations (JSON), scheduling_window (JSON), query_modifications (JSON)</p>
				</div>
				<div class="bg-gray-50 rounded-lg p-4">
					<p class="font-medium text-gray-900 mb-1">Query</p>
					<p class="text-gray-600">id, project_id (FK), text, url, click_url, geo (JSON), daily_clicks, position, completed, frequency</p>
				</div>
				<div class="bg-gray-50 rounded-lg p-4">
					<p class="font-medium text-gray-900 mb-1">QueueTask</p>
					<p class="text-gray-600">id, project_id (FK), query_id (FK), task_key, status (pending/in_progress/completed/not_found/stuck), source (strategy/autoburst/proklik), geo (JSON), position, created_at</p>
				</div>
			</div>
		</section>

		<section class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
			<h2 class="text-xl font-semibold text-gray-900 mb-4">Настройки внешних сервисов (JSON)</h2>
			<div class="space-y-3 text-sm">
				<div class="bg-gray-50 rounded-lg p-4 font-mono text-xs overflow-x-auto">
{
  "xml_river": {
    "user_id": "string",
    "apk": "string"
  },
  "xml_stock": [
    {
      "name": "key_name_1",
      "api_key": "string"
    }
  ]
}
				</div>
			</div>
		</section>
	</div>
</div>
