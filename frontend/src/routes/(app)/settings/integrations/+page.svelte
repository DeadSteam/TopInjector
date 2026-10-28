<script lang="ts">
	import { api } from "$lib/api";
	import { onMount } from "svelte";

	// State
	let groups = $state<any[]>([]);
	let loading = $state(true);
	let error = $state("");
	let saving = $state(false);
	let showCreateForm = $state(false);
	let expandedGroupId = $state<string | null>(null);
	let selectedGroupId = $state<string | null>(null);

	// Create group form
	let newGroupName = $state("");
	let newGroupMaxProjects = $state(10);
	let newGroupRpmLimit = $state(300);
	let newGroupIpWhitelist = $state("");
	let newGroupUseReserved = $state(false);
	let newGroupIsPublic = $state(false);

	// Edit group form
	let editingGroupId = $state<string | null>(null);
	let editGroupName = $state("");
	let editGroupMaxProjects = $state(10);
	let editGroupRpmLimit = $state(300);
	let editGroupUseReserved = $state(false);
	let editGroupIsPublic = $state(false);
	let editGroupIsActive = $state(true);

	// Server management
	let servers = $state<any[]>([]);
	let serverLoading = $state(false);
	let newServerName = $state("");
	let newServerIp = $state("");
	let newServerType = $state("portal");
	let newServerQpm = $state(60);
	let newServerNotes = $state("");
	let creatingServer = $state(false);

	// Edit server form
	let editingServerId = $state<string | null>(null);
	let editServerName = $state("");
	let editServerIp = $state("");
	let editServerType = $state("portal");
	let editServerQpm = $state(60);
	let editServerNotes = $state("");
	let editServerActive = $state(true);
	let updatingServer = $state(false);

	// Projects list (for assignment)
	let projects = $state<any[]>([]);
	let loadingProjects = $state(false);

	const SOFTWARE_TYPES = [
		{ value: "alpine", label: "Alpine" },
		{ value: "monstro", label: "Monstro" },
		{ value: "portal", label: "Portal" },
		{ value: "fantom", label: "Fantom" },
	];

	async function loadGroups() {
		loading = true;
		error = "";
		try {
			groups = (await api.integrationGroups.list()).groups || [];
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка загрузки групп";
		} finally {
			loading = false;
		}
	}

	async function loadProjects() {
		loadingProjects = true;
		try {
			projects = await api.projects.all();
		} catch {
			projects = [];
		} finally {
			loadingProjects = false;
		}
	}

	function resetNewGroupForm() {
		newGroupName = "";
		newGroupMaxProjects = 10;
		newGroupRpmLimit = 300;
		newGroupIpWhitelist = "";
		newGroupUseReserved = false;
		newGroupIsPublic = false;
		showCreateForm = false;
	}

	async function createGroup() {
		if (!newGroupName.trim()) { error = "Укажите название группы"; return; }
		saving = true;
		error = "";
		try {
			const ipList = newGroupIpWhitelist
				? newGroupIpWhitelist.split(",").map((s: string) => s.trim()).filter(Boolean)
				: [];
			await api.integrationGroups.create({
				name: newGroupName.trim(),
				max_projects: Number(newGroupMaxProjects),
				rpm_limit: Number(newGroupRpmLimit),
				ip_whitelist: ipList,
				use_reserved: newGroupUseReserved,
				is_public: newGroupIsPublic,
			});
			resetNewGroupForm();
			await loadGroups();
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка создания группы";
		} finally {
			saving = false;
		}
	}

	async function updateGroup(group: any) {
		if (!editGroupName.trim()) { error = "Укажите название группы"; return; }
		saving = true;
		error = "";
		try {
			await api.integrationGroups.update(editingGroupId!, {
				name: editGroupName.trim(),
				max_projects: Number(editGroupMaxProjects),
				rpm_limit: Number(editGroupRpmLimit),
				use_reserved: editGroupUseReserved,
				is_public: editGroupIsPublic,
				is_active: editGroupIsActive,
			});
			editingGroupId = null;
			await loadGroups();
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка обновления группы";
		} finally {
			saving = false;
		}
	}

	async function deleteGroup(id: string) {
		if (!confirm("Удалить группу? Проекты будут отвязаны.")) return;
		try {
			await api.integrationGroups.delete(id);
			if (expandedGroupId === id) { expandedGroupId = null; servers = []; }
			await loadGroups();
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка удаления группы";
		}
	}

	async function toggleExpand(groupId: string) {
		if (expandedGroupId === groupId) {
			expandedGroupId = null;
			servers = [];
			return;
		}
		expandedGroupId = groupId;
		await loadServers(groupId);
	}

	async function selectGroupForAssign(groupId: string) {
		selectedGroupId = selectedGroupId === groupId ? null : groupId;
	}

	function startEditGroup(group: any) {
		editingGroupId = group.id;
		editGroupName = group.name;
		editGroupMaxProjects = group.max_projects;
		editGroupRpmLimit = group.rpm_limit;
		editGroupUseReserved = group.use_reserved || false;
		editGroupIsPublic = group.is_public || false;
		editGroupIsActive = group.is_active !== false;
	}

	function cancelEditGroup() {
		editingGroupId = null;
	}

	async function loadServers(groupId: string) {
		serverLoading = true;
		try {
			servers = (await api.integrationGroups.servers(groupId)).servers || [];
		} catch {
			servers = [];
		} finally {
			serverLoading = false;
		}
	}

	function resetNewServerForm() {
		newServerName = "";
		newServerIp = "";
		newServerType = "portal";
		newServerQpm = 60;
		newServerNotes = "";
		creatingServer = false;
	}

	async function createServer(groupId: string) {
		if (!newServerName.trim()) { error = "Укажите название сервера"; return; }
		creatingServer = true;
		error = "";
		try {
			await api.integrationGroups.createServer(groupId, {
				name: newServerName.trim(),
				ip_address: newServerIp || null,
				software_type: newServerType,
				max_queries_per_minute: Number(newServerQpm),
				notes: newServerNotes || undefined,
			});
			resetNewServerForm();
			await loadServers(groupId);
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка создания сервера";
		} finally {
			creatingServer = false;
		}
	}

	function startEditServer(server: any) {
		editingServerId = server.id;
		editServerName = server.name;
		editServerIp = server.ip_address || "";
		editServerType = server.software_type;
		editServerQpm = server.max_queries_per_minute;
		editServerNotes = server.notes || "";
		editServerActive = server.is_active !== false;
	}

	function cancelEditServer() {
		editingServerId = null;
	}

	async function updateServer(groupId: string, serverId: string) {
		if (!editServerName.trim()) { error = "Укажите название сервера"; return; }
		updatingServer = true;
		error = "";
		try {
			await api.integrationGroups.updateServer(groupId, serverId, {
				name: editServerName.trim(),
				ip_address: editServerIp || null,
				software_type: editServerType,
				max_queries_per_minute: Number(editServerQpm),
				notes: editServerNotes || undefined,
				is_active: editServerActive,
			});
			editingServerId = null;
			await loadServers(groupId);
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка обновления сервера";
		} finally {
			updatingServer = false;
		}
	}

	async function deleteServer(groupId: string, serverId: string) {
		if (!confirm("Удалить этот сервер?")) return;
		try {
			await api.integrationGroups.deleteServer(groupId, serverId);
			await loadServers(groupId);
		} catch (e) {
			error = e instanceof Error ? e.message : "Ошибка удаления сервера";
		}
	}

	function typeLabel(t: string) {
		return SOFTWARE_TYPES.find(s => s.value === t)?.label || t;
	}

	onMount(() => { loadGroups(); });
</script>

<div class="p-6">
	<h1 class="text-2xl font-bold text-gray-900 mb-1">Интеграции (Серверные группы)</h1>
	<p class="text-sm text-gray-500 mb-6">Управление серверными группами и серверами для привязки проектов.</p>

	{#if error}
		<div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">{error}</div>
	{/if}

	<!-- Create group button / form -->
	{#if !showCreateForm}
		<button onclick={() => (showCreateForm = true)} class="mb-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
			+ Создать группу
		</button>
	{:else}
		<div class="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-4">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Новая серверная группа</h2>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">Название *</label>
					<input bind:value={newGroupName} placeholder="Ryzen7 PowerVPS" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
				</div>
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">Лимит проектов</label>
					<input type="number" bind:value={newGroupMaxProjects} min="1" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
				</div>
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">RPM лимит</label>
					<input type="number" bind:value={newGroupRpmLimit} min="1" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" />
				</div>
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1">IP whitelist (через запятую)</label>
					<input bind:value={newGroupIpWhitelist} placeholder="1.2.3.4, 5.6.7.8" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm font-mono" />
				</div>
			</div>
			<div class="mt-4 flex gap-4">
				<label class="flex items-center gap-2 text-sm text-gray-700">
					<input type="checkbox" bind:checked={newGroupUseReserved} class="rounded border-gray-300" />
					Использовать резервные сервера
				</label>
				<label class="flex items-center gap-2 text-sm text-gray-700">
					<input type="checkbox" bind:checked={newGroupIsPublic} class="rounded border-gray-300" />
					Публичная группа (витрина)
				</label>
			</div>
			<div class="mt-4 flex gap-2">
				<button onclick={createGroup} disabled={saving} class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors">
					{saving ? "Создание..." : "Создать"}
				</button>
				<button onclick={resetNewGroupForm} class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50 transition-colors">Отмена</button>
			</div>
		</div>
	{/if}

	<!-- Groups list -->
	{#if loading}
		<div class="text-center py-12 text-gray-400">Загрузка...</div>
	{:else if groups.length === 0}
	 <div class="bg-white border border-gray-200 rounded-xl shadow-sm p-8 text-center">
			<p class="text-gray-400">Нет серверных групп</p>
			<p class="text-sm text-gray-500 mt-1">Создайте первую группу для управления проектами</p>
		</div>
	{:else}
		<div class="space-y-3">
			{#each groups as group (group.id)}
				<div class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
					<!-- Group header -->
					<div class="flex items-center justify-between p-4">
						<div class="flex items-center gap-3 flex-1 min-w-0">
							<button onclick={() => toggleExpand(group.id)} class="flex-shrink-0 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-gray-600">
								<svg class="w-4 h-4 transition-transform {expandedGroupId === group.id ? 'rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
							</button>
							<div class="flex-1 min-w-0">
								<p class="font-medium text-gray-900 truncate">{group.name}</p>
								<p class="text-xs text-gray-500">
									{group.current_project_count}/{group.max_projects} проектов · {group.server_count} серверов · RPM: {group.rpm_limit}
								</p>
							</div>
						</div>

						<!-- Action buttons -->
						<div class="flex gap-2 flex-shrink-0">
							{#if editingGroupId === group.id}
								<button onclick={() => updateGroup(group)} disabled={saving} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs transition-colors">
									{saving ? "..." : "Сохранить"}
								</button>
								<button onclick={cancelEditGroup} class="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg text-xs hover:bg-gray-50 transition-colors">Отмена</button>
							{:else}
								<button onclick={() => selectGroupForAssign(group.id)} class="px-3 py-1.5 text-xs {selectedGroupId === group.id ? 'bg-blue-600 text-white' : 'border border-gray-300 text-gray-600 hover:bg-gray-50'} rounded-lg transition-colors">
									{selectedGroupId === group.id ? 'Выбрана' : 'Выбрать'}
								</button>
								<button onclick={() => startEditGroup(group)} class="px-3 py-1.5 border border-gray-300 text-gray-600 hover:bg-gray-50 rounded-lg text-xs transition-colors">Изменить</button>
								<button onclick={() => deleteGroup(group.id)} class="px-3 py-1.5 border border-red-300 text-red-600 hover:bg-red-50 rounded-lg text-xs transition-colors">Удалить</button>
							{/if}
						</div>
					</div>

					<!-- Expandable: edit form -->
					{#if editingGroupId === group.id}
						<div class="border-t border-gray-100 p-4 bg-gray-50">
							<h3 class="text-sm font-medium text-gray-900 mb-3">Редактировать группу</h3>
							<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
								<div>
									<label class="block text-xs text-gray-600 mb-1">Название</label>
									<input bind:value={editGroupName} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
								</div>
								<div>
									<label class="block text-xs text-gray-600 mb-1">Лимит проектов</label>
									<input type="number" bind:value={editGroupMaxProjects} min="1" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
								</div>
								<div>
									<label class="block text-xs text-gray-600 mb-1">RPM лимит</label>
									<input type="number" bind:value={editGroupRpmLimit} min="1" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
								</div>
							</div>
							<div class="mt-3 flex gap-4">
								<label class="flex items-center gap-2 text-xs text-gray-700">
									<input type="checkbox" bind:checked={editGroupUseReserved} class="rounded border-gray-300" />
									Резервные сервера
								</label>
								<label class="flex items-center gap-2 text-xs text-gray-700">
									<input type="checkbox" bind:checked={editGroupIsPublic} class="rounded border-gray-300" />
									Публичная группа
								</label>
								<label class="flex items-center gap-2 text-xs text-gray-700">
									<input type="checkbox" bind:checked={editGroupIsActive} class="rounded border-gray-300" />
									Активна
								</label>
							</div>
						</div>
					{/if}

					<!-- Expandable: servers list -->
					{#if expandedGroupId === group.id}
						<div class="border-t border-gray-100">
							<div class="p-4">
								<div class="flex items-center justify-between mb-3">
									<h3 class="text-sm font-medium text-gray-900">Серверы группы</h3>
									<button onclick={() => { creatingServer = true; }} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs transition-colors">+ Сервер</button>
								</div>

								{#if creatingServer}
									<div class="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-3">
										<h4 class="text-sm font-medium text-gray-900 mb-3">Новый сервер</h4>
										<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
											<div>
												<label class="block text-xs text-gray-600 mb-1">Название *</label>
												<input bind:value={newServerName} placeholder="Monstro-1" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
											</div>
											<div>
												<label class="block text-xs text-gray-600 mb-1">IP адрес</label>
												<input bind:value={newServerIp} placeholder="1.2.3.4" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
											</div>
											<div>
												<label class="block text-xs text-gray-600 mb-1">Тип ПО</label>
												<select bind:value={newServerType} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
													{#each SOFTWARE_TYPES as s}<option value={s.value}>{s.label}</option>{/each}
												</select>
											</div>
											<div>
												<label class="block text-xs text-gray-600 mb-1">RPM лимит сервера</label>
												<input type="number" bind:value={newServerQpm} min="1" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
											</div>
											<div class="md:col-span-2">
												<label class="block text-xs text-gray-600 mb-1">Заметки</label>
												<input bind:value={newServerNotes} placeholder="Доп. информация о сервере" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
											</div>
										</div>
										<div class="mt-3 flex gap-2">
											<button onclick={() => createServer(group.id)} disabled={creatingServer} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs transition-colors">
												{creatingServer ? "Создание..." : "Создать сервер"}
											</button>
											<button onclick={() => { creatingServer = false; resetNewServerForm(); }} class="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg text-xs hover:bg-gray-50 transition-colors">Отмена</button>
										</div>
									</div>
								{/if}

								{#if serverLoading}
									<div class="text-center py-4 text-sm text-gray-400">Загрузка...</div>
								{:else if servers.length === 0}
									<p class="text-sm text-gray-400 text-center py-2">Нет серверов в группе</p>
								{:else}
									<div class="space-y-2">
										{#each servers as server (server.id)}
											<div class="border border-gray-200 rounded-lg p-3">
												{#if editingServerId === server.id}
													<!-- Edit server form -->
													<div class="grid grid-cols-1 md:grid-cols-2 gap-2">
														<div>
															<label class="block text-xs text-gray-600 mb-1">Название</label>
															<input bind:value={editServerName} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
														</div>
														<div>
															<label class="block text-xs text-gray-600 mb-1">IP адрес</label>
															<input bind:value={editServerIp} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none" />
														</div>
														<div>
															<label class="block text-xs text-gray-600 mb-1">Тип ПО</label>
															<select bind:value={editServerType} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
																{#each SOFTWARE_TYPES as s}<option value={s.value}>{s.label}</option>{/each}
															</select>
														</div>
														<div>
															<label class="block text-xs text-gray-600 mb-1">RPM сервера</label>
															<input type="number" bind:value={editServerQpm} min="1" class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
														</div>
														<div class="md:col-span-2">
															<label class="block text-xs text-gray-600 mb-1">Заметки</label>
															<input bind:value={editServerNotes} class="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
														</div>
													</div>
													<div class="mt-2 flex items-center gap-3">
														<label class="flex items-center gap-2 text-xs text-gray-700">
															<input type="checkbox" bind:checked={editServerActive} class="rounded border-gray-300" /> Активен
														</label>
														<button onclick={() => updateServer(group.id, server.id)} disabled={updatingServer} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs transition-colors">
															{updatingServer ? "..." : "Сохранить"}
														</button>
														<button onclick={cancelEditServer} class="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg text-xs hover:bg-gray-50 transition-colors">Отмена</button>
													</div>
												{:else}
													<!-- Server display -->
													<div class="flex items-center justify-between">
														<div class="flex-1 min-w-0">
															<div class="flex items-center gap-2">
																<p class="text-sm font-medium text-gray-900">{server.name}</p>
																<span class="px-1.5 py-0.5 rounded text-[10px] font-medium {server.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}">
																	{server.is_active ? "активен" : "неактивен"}
																</span>
															</div>
															<div class="flex items-center gap-3 mt-0.5">
																<span class="text-xs text-gray-500">{typeLabel(server.software_type)}</span>
																{#if server.ip_address}<span class="text-xs font-mono text-gray-400">{server.ip_address}</span>{/if}
																<span class="text-xs text-gray-500">RPM: {server.max_queries_per_minute}</span>
															</div>
															{#if server.notes}<p class="text-xs text-gray-400 mt-1 truncate">{server.notes}</p>{/if}
														</div>
														<div class="flex gap-2 flex-shrink-0">
															<button onclick={() => startEditServer(server)} class="px-3 py-1.5 text-xs border border-gray-300 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors">Изменить</button>
															<button onclick={() => deleteServer(group.id, server.id)} class="px-3 py-1.5 text-xs border border-red-300 text-red-600 hover:bg-red-50 rounded-lg transition-colors">Удалить</button>
														</div>
													</div>
												{/if}
											</div>
										{/each}
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	<!-- Selected group assignment -->
	{#if selectedGroupId}
		<div class="mt-4 bg-white border border-blue-200 rounded-xl shadow-sm p-4">
			<h3 class="text-sm font-medium text-gray-900 mb-3">Выбранная группа: {groups.find((g: any) => g.id === selectedGroupId)?.name}</h3>
			<p class="text-xs text-gray-500 mb-3">Привяжите проекты к этой группе через страницу проектов</p>
			{#if loadingProjects}
				<p class="text-sm text-gray-400">Загрузка...</p>
			{:else}
				<div class="space-y-1">
					{#each projects as project (project.id)}
						<div class="flex items-center justify-between py-1.5 px-2 rounded hover:bg-gray-50">
							<span class="text-sm text-gray-700">{project.name} <span class="text-xs text-gray-400">({project.domain})</span></span>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
