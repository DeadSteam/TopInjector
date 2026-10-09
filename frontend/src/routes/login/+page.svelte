<script lang="ts">
	import { api } from "$lib/api";
	import { goto } from '$app/navigation';

	let email = $state("");
	let password = $state("");
	let displayName = $state("");
	let loading = $state(false);
	let error = $state("");
	let isRegister = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!email || !password) {
			error = "Введите email и пароль";
			return;
		}
		if (isRegister && !displayName) {
			error = "Введите имя";
			return;
		}
		loading = true;
		error = "";
		try {
			let res: any;
			if (isRegister) {
				res = await api.auth.register(email, password, displayName);
			} else {
				res = await api.auth.login(email, password);
			}
			localStorage.setItem("token", res.access_token);
			localStorage.setItem("refresh_token", res.refresh_token);
			goto("/");
		} catch (err) {
			error = err instanceof Error ? err.message : "Ошибка";
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e293b] to-[#0f172a]">
	<div class="w-full max-w-md p-8 bg-white rounded-2xl shadow-xl">
		<div class="text-center mb-8">
			<h1 class="text-2xl font-bold text-gray-900">
				<span class="text-blue-600">Top</span>Injector
			</h1>
			<p class="text-sm text-gray-500 mt-2">{isRegister ? "Регистрация" : "Вход в аккаунт"}</p>
		</div>

		{#if error}
			<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
				{error}
			</div>
		{/if}

		<form onsubmit={handleSubmit} class="space-y-4">
			{#if isRegister}
				<div>
					<label for="displayName" class="block text-sm font-medium text-gray-700 mb-1">Имя</label>
					<input id="displayName" type="text" bind:value={displayName} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all" placeholder="Ваше имя"/>
				</div>
			{/if}

			<div>
				<label for="email" class="block text-sm font-medium text-gray-700 mb-1">Email</label>
				<input id="email" type="email" bind:value={email} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all" placeholder="user@example.com" required/>
			</div>

			<div>
				<label for="password" class="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
				<input id="password" type="password" bind:value={password} class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all" placeholder="••••••••" required minlength="8"/>
			</div>

			<button type="submit" disabled={loading} class="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
				{loading ? (isRegister ? "Регистрация..." : "Вход...") : (isRegister ? "Зарегистрироваться" : "Войти")}
			</button>
		</form>

		<div class="mt-4 text-center text-sm">
			<span class="text-gray-500">{isRegister ? "Уже есть аккаунт?" : "Нет аккаунта?"}</span>
			<button type="button" onclick={() => { isRegister = !isRegister; error = ""; }} class="ml-2 text-blue-600 hover:text-blue-500 font-medium">
				{isRegister ? "Войти" : "Зарегистрироваться"}
			</button>
		</div>

		<div class="mt-6 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-800">
			Используем файлы cookie для улучшения работы платформы.
		</div>
	</div>
</div>
