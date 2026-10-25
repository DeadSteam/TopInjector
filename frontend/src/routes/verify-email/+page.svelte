<script lang="ts">
	import { onMount } from "svelte";

	// Landing page of the link from the verification e-mail: /verify-email?token=...
	let status = $state<"loading" | "ok" | "error">("loading");
	let message = $state("Проверяем ссылку...");

	onMount(async () => {
		const token = new URLSearchParams(window.location.search).get("token");
		if (!token) {
			status = "error";
			message = "В ссылке нет кода подтверждения.";
			return;
		}
		try {
			const res = await fetch("/api/auth/verify-email", {
				method: "POST",
				headers: { Authorization: `Bearer ${token}` },
			});
			const body = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(body.detail || res.statusText);
			status = "ok";
			message = body.message === "Email already verified" ? "Почта уже была подтверждена." : "Почта подтверждена.";
		} catch {
			status = "error";
			message = "Ссылка недействительна или устарела: она действует 30 минут после регистрации.";
		}
	});
</script>

<div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e293b] to-[#0f172a]">
	<div class="w-full max-w-md p-8 bg-white rounded-2xl shadow-xl text-center">
		<h1 class="text-2xl font-bold text-gray-900 mb-2">
			<span class="text-blue-600">Top</span>Injector
		</h1>
		<p class="text-sm text-gray-500 mb-6">Подтверждение почты</p>
		<p class="text-sm {status === 'error' ? 'text-red-600' : status === 'ok' ? 'text-green-700' : 'text-gray-600'}">{message}</p>
		{#if status !== "loading"}
			<a href="/login" class="inline-block mt-6 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
				Перейти ко входу
			</a>
		{/if}
	</div>
</div>
