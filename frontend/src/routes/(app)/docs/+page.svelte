<script context="module" lang="ts">
	declare const Redoc: any;
</script>
<script lang="ts">
	import { onMount } from 'svelte';

	onMount(() => {
		const script = document.createElement('script');
		script.src = 'https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js';
		script.onload = () => {
			if (typeof Redoc === 'undefined') return;
			const el = document.getElementById('redoc-container');
			if (!el) return;

			fetch("/api/openapi.json")
				.then(r => r.json())
				.then((spec) => {
					const opts = {
						showExtensions: true,
						sortPropsAlphabetically: true,
						theme: { rightPanelBackgroundColor: '#1e293b', sizes: { baseFontSize: '14px' } },
					};
					Redoc.init(spec, opts, el);
				})
				.catch(() => {
					const fallback = document.getElementById('fallback-docs');
					if (fallback) fallback.style.display = 'block';
				});
		};
		document.head.appendChild(script);
	});
</script>

<div class="p-6 max-w-[1600px]">
	<h1 class="text-2xl font-bold text-gray-900 mb-6">API Документация</h1>

	<p class="text-sm text-gray-500 mb-4">Интерактивная документация API TopInjector (OpenAPI). Её же можно открыть в Swagger: /api/docs.</p>

	<!-- Redoc container -->
	<div id="redoc-container" class="bg-white border border-gray-200 rounded-xl shadow-sm min-h-[600px]"></div>

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
					<p class="text-sm text-gray-600">Создание проекта. Тело: <code class="text-xs">&#123; name, domain, region, schedule_type &#125;</code></p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-bold">PUT</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/projects/{"{"}id{"}"}</span>
					</div>
					<p class="text-sm text-gray-600">Обновление проекта.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/terms/upsert</span>
					</div>
					<p class="text-sm text-gray-600">Добавление/обновление запросов по тексту (существующие сохраняют id). Тело: {"{"} queries: [{"{"} text, url, click_url, geo, daily_clicks {"}"}] {"}"}.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/queue/push</span>
					</div>
					<p class="text-sm text-gray-600">Добавление задач в очередь проекта токена. Тело: <code class="bg-gray-100 px-1 rounded">&#123; tasks: [&#123; click_url, query_id?, source?, geo? &#125;] &#125;</code>.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/queue/results</span>
					</div>
					<p class="text-sm text-gray-600">Взять задачи в работу: <code class="bg-gray-100 px-1 rounded">POST /queue/claim &#123; limit &#125;</code> (переводит их в in_progress). Отправка результатов: <code class="bg-gray-100 px-1 rounded">&#123; results: [&#123; task_id, status, position? &#125;] &#125;</code>.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-pink-100 text-pink-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/users</span>
					</div>
					<p class="text-sm text-gray-600">Пользователи организации — пока не реализовано (ответ 501).</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/balance/add</span>
					</div>
					<p class="text-sm text-gray-600">Пополнить баланс проекта токена (в рублях). Тело: {"{"} amount {"}"}.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/balance/set</span>
					</div>
					<p class="text-sm text-gray-600">Установить баланс проекта токена (в рублях). Тело: {"{"} balance {"}"}.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-bold">GET</span>
						<span class="font-mono text-sm text-gray-900">/api/external/v1/health</span>
					</div>
					<p class="text-sm text-gray-600">Проверка доступности API. Возвращает <code class="bg-gray-100 px-1 rounded">&#123; status: "ok" &#125;</code>.</p>
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
					<p class="text-sm text-gray-600">Вход. Тело: {"{"} email, password {"}"}.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/auth/register</span>
					</div>
					<p class="text-sm text-gray-600">Регистрация. Тело: {"{"} email, password, display_name {"}"}.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/auth/refresh</span>
					</div>
					<p class="text-sm text-gray-600">Обновление токена. Тело: {"{"} refresh_token {"}"}.</p>
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
					<p class="text-sm text-gray-600">Обновить профиль. Тело: {"{"} display_name {"}"}.</p>
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
					<p class="text-sm text-gray-600">Сменить пароль. Тело: {"{"} current_password, new_password {"}"}.</p>
				</div>

				<div class="border border-gray-200 rounded-lg p-4">
					<div class="flex items-center gap-2 mb-1">
						<span class="px-2 py-0.5 bg-cyan-100 text-cyan-700 rounded text-xs font-bold">POST</span>
						<span class="font-mono text-sm text-gray-900">/api/projects/{"{"}id{"}"}/queries/bulk-update</span>
					</div>
					<p class="text-sm text-gray-600">Массовое обновление запросов. Тело: <code class="bg-gray-100 px-1 rounded">&#123; query_ids, daily_clicks?, geo?, click_url? &#125;</code>.</p>
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
<span>&#123;

  "xml_river": &#123;

    "user_id": "string",

    "apk": "string"

  &#125;,

  "xml_stock": [

    &#123;

      "name": "key_name_1",

      "api_key": "string"

    &#125;

  ]

&#125;
</span>
				</div>
			</div>
		</section>
	</div>
</div>
