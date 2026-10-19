/** API client for TopInjector backend. */

// In production, use relative paths so nginx handles routing.
// In dev (or Docker), VITE_API_URL points to the backend for direct access.
const BASE_URL = import.meta.env.VITE_API_URL && import.meta.env.VITE_API_URL !== "/"
	? import.meta.env.VITE_API_URL
	: "";
let refreshTokenFns: Array<{ resolve: (v: string) => void; reject: (e: Error) => void }> = [];
let refreshingPromise: Promise<string> | null = null;

function headers(token?: string): HeadersInit {
	const h: HeadersInit = { "Content-Type": "application/json" };
	if (token) h["Authorization"] = `Bearer ${token}`;
	return h;
}

async function _refresh(): Promise<string> {
	const rt = localStorage.getItem("refresh_token");
	if (!rt) throw new Error("No refresh token");
	const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ refresh_token: rt }),
	});
	if (!res.ok) throw new Error("Refresh failed");
	const data = await res.json();
	localStorage.setItem("token", data.access_token);
	localStorage.setItem("refresh_token", data.refresh_token);
	return data.access_token;
}

async function fetcher(path: string, options?: RequestInit): Promise<any> {
	// Auto-refresh token on 401 before calling this
	let token = localStorage.getItem("token") || "";

	const res = await fetch(`${BASE_URL}${path}`, {
		...options,
		headers: { ...headers(token), ...options?.headers },
	});

	if (res.status === 401 && token) {
		// Token expired — try refresh
		try {
			token = await _refresh();
			// Retry original request with new token
			const retryRes = await fetch(`${BASE_URL}${path}`, {
				...options,
				headers: { ...headers(token), ...options?.headers },
			});
			if (!retryRes.ok) {
				const body = await retryRes.json().catch(() => ({}));
				throw new Error(body.detail || retryRes.statusText);
			}
			return retryRes.json();
		} catch {
			// Refresh failed — clear tokens and redirect
			localStorage.removeItem("token");
			localStorage.removeItem("refresh_token");
			window.location.href = "/login";
			throw new Error("Session expired");
		}
	}

	if (!res.ok) {
		const body = await res.json().catch(() => ({}));
		throw new Error(body.detail || res.statusText);
	}
	return res.json();
}

export const api = {
	auth: {
		login: (email: string, password: string) =>
			fetcher("/api/auth/login", {
				method: "POST",
				body: JSON.stringify({ email, password }),
			}),
		register: (email: string, password: string, displayName: string) =>
			fetcher("/api/auth/register", {
				method: "POST",
				body: JSON.stringify({ email, password, display_name: displayName }),
			}),
		refresh: (refreshToken: string) =>
			fetcher("/api/auth/refresh", {
				method: "POST",
				body: JSON.stringify({ refresh_token: refreshToken }),
			}),
		me: () => fetcher("/api/auth/me"),
		logout: () => {
			localStorage.removeItem("token");
			localStorage.removeItem("refresh_token");
			window.location.href = "/login";
		},
	},
	projects: {
		list: (params?: { search?: string; group_id?: string; region?: string; strategy_type?: string; is_active?: boolean; only_delegated?: string; delegated_by?: string; page?: number; page_size?: number }) => {
			let path = "/api/projects/";
			if (params) {
				const qs = new URLSearchParams();
				if (params.search) qs.set("search", params.search);
				if (params.group_id) qs.set("group_id", params.group_id);
				if (params.region) qs.set("region", params.region);
				if (params.strategy_type) qs.set("strategy_type", params.strategy_type);
				if (params.is_active !== undefined) qs.set("is_active", String(params.is_active));
				if (params.only_delegated) qs.set("only_delegated", params.only_delegated);
				if (params.delegated_by) qs.set("delegated_by", params.delegated_by);
				if (params.page) qs.set("page", String(params.page));
				if (params.page_size) qs.set("page_size", String(params.page_size));
				path += "?" + qs.toString();
			}
			return fetcher(path);
		},
		get: (id: string) => fetcher(`/api/projects/${id}`),
		create: (data: any) =>
			fetcher("/api/projects/", { method: "POST", body: JSON.stringify(data) }),
		update: (id: string, data: any) =>
			fetcher(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify(data) }),
		delete: (id: string) =>
			fetcher(`/api/projects/${id}`, { method: "DELETE" }),
		activate: (id: string, active: boolean) =>
			fetcher(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify({ is_active: active }) }),
		queries: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/queries`),
		addQuery: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/queries`, {
				method: "POST",
				body: JSON.stringify(data),
			}),
		updateQuery: (projectId: string, queryId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/queries/${queryId}`, {
				method: "PUT",
				body: JSON.stringify(data),
			}),
		deleteQuery: (projectId: string, queryId: string) =>
			fetcher(`/api/projects/${projectId}/queries/${queryId}`, {
				method: "DELETE",
			}),
		importQueries: (projectId: string, csvText: string) =>
			fetcher(`/api/projects/${projectId}/queries/import`, {
				method: "POST",
				headers: { "Content-Type": "text/csv" },
				body: csvText,
			}),
		boost: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/boost`, {
				method: "POST",
				body: JSON.stringify(data),
			}),
		requestTable: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/request-table`),
		queueStats: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/queue-stats`),
		queueStatsBySource: (projectId: string) =>
			fetcher(`/api/queue/stats/source?project_id=${projectId}`),
		positions: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/positions`),
		trend: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/trend`),
		markers: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/markers`),
		createMarker: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/markers`, { method: "POST", body: JSON.stringify(data) }),
		updateMarker: (projectId: string, markerId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/markers/${markerId}`, { method: "PUT", body: JSON.stringify(data) }),
		deleteMarker: (projectId: string, markerId: string) =>
			fetcher(`/api/projects/${projectId}/markers/${markerId}`, { method: "DELETE" }),
		webmarkers: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/webmarkers`),
		createWebmarker: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/webmarkers`, { method: "POST", body: JSON.stringify(data) }),
		updateWebmarker: (projectId: string, webmarkerId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/webmarkers/${webmarkerId}`, { method: "PUT", body: JSON.stringify(data) }),
		verifyWebmarker: (projectId: string, webmarkerId: string) =>
			fetcher(`/api/projects/${projectId}/webmarkers/${webmarkerId}/verify`, { method: "POST" }),
		deleteWebmarker: (projectId: string, webmarkerId: string) =>
			fetcher(`/api/projects/${projectId}/webmarkers/${webmarkerId}`, { method: "DELETE" }),
		delegates: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/delegates`),
		addDelegate: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/delegates`, { method: "POST", body: JSON.stringify(data) }),
		removeDelegate: (projectId: string, delegateUserId: string) =>
			fetcher(`/api/projects/${projectId}/delegates/${delegateUserId}`, { method: "DELETE" }),
		overdueCount: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/overdue-count`),
		sourceBreakdown: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/source-breakdown`),
		copyProject: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/copy`, { method: "POST", body: JSON.stringify(data) }),
		clearQueue: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/clear-queue`, { method: "POST", body: JSON.stringify(data) }),
		getClicks: (projectId: string, params?: { date_str?: string; source?: string; geo?: string; suggestion_mode?: string }) => {
			let path = `/api/projects/${projectId}/clicks`;
			if (params) {
				const qs = new URLSearchParams();
				if (params.date_str) qs.set("date_str", params.date_str);
				if (params.source) qs.set("source", params.source);
				if (params.geo) qs.set("geo", params.geo);
				if (params.suggestion_mode) qs.set("suggestion_mode", params.suggestion_mode);
				path += "?" + qs.toString();
			}
			return fetcher(path);
		},
		getAuditLog: (projectId: string, page: number, pageSize: number, geo?: string, suggestionMode?: string) => {
			let path = `/api/projects/${projectId}/audit-log?page=${page}&page_size=${pageSize}`;
			if (geo) path += `&geo=${encodeURIComponent(geo)}`;
			if (suggestionMode) path += `&suggestion_mode=${encodeURIComponent(suggestionMode)}`;
			return fetcher(path);
		},
		bulkUpdateQueries: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/queries/bulk-update`, { method: "POST", body: JSON.stringify(data) }),
		globalSearch: (q: string) =>
			fetcher(`/api/projects/global-search?q=${encodeURIComponent(q)}`),
		bulkToggle: (data: { project_ids: string[]; is_active: boolean }) =>
			fetcher("/api/projects/bulk-toggle", { method: "POST", body: JSON.stringify(data) }),
		bulkEdit: (data: { project_ids: string[]; [key: string]: any }) =>
			fetcher("/api/projects/bulk-edit", { method: "POST", body: JSON.stringify(data) }),
		bulkDelete: (data: { project_ids: string[] }) =>
			fetcher("/api/projects/bulk-delete", { method: "POST", body: JSON.stringify(data) }),
		bulkDelegate: (data: { project_ids: string[]; delegate_user_id: string; role: string }) =>
			fetcher("/api/projects/bulk-delegate", { method: "POST", body: JSON.stringify(data) }),
		reportAnalytics: (projectId: string, params?: { from_date?: string; to_date?: string }) => {
			let path = `/api/projects/${projectId}/reports/analytics.csv`;
			if (params) {
				const qs = new URLSearchParams();
				if (params.from_date) qs.set("from_date", params.from_date);
				if (params.to_date) qs.set("to_date", params.to_date);
				path += "?" + qs.toString();
			}
			return fetch(path).then(r => r.blob());
		},
		reportSummary: (projectId: string, params?: { from_date?: string; to_date?: string }) => {
			let path = `/api/projects/${projectId}/reports/summary.csv`;
			if (params) {
				const qs = new URLSearchParams();
				if (params.from_date) qs.set("from_date", params.from_date);
				if (params.to_date) qs.set("to_date", params.to_date);
				path += "?" + qs.toString();
			}
			return fetch(path).then(r => r.blob());
		},
		autoStop: (projectId: string, data: { auto_stop_at?: string | null }) =>
			fetcher(`/api/projects/${projectId}/auto-stop`, { method: "PUT", body: JSON.stringify(data) }),
		getAutoStop: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/auto-stop`),
		integrations: () =>
			fetcher("/api/projects/integrations"),
		geoCodesSearch: (q: string, limit: number = 20) =>
			fetcher(`/api/projects/geo-codes/search?q=${encodeURIComponent(q)}&limit=${limit}`),
		adminStats: () => fetcher("/api/projects/admin/stats"),
	},
	warmups: {
		list: (projectId?: string) => {
			let path = "/api/warmups";
			if (projectId) path += `?project_id=${encodeURIComponent(projectId)}`;
			return fetcher(path);
		},
		create: (data: any) =>
			fetcher("/api/warmups", { method: "POST", body: JSON.stringify(data) }),
		update: (id: string, data: any) =>
			fetcher(`/api/warmups/${id}`, { method: "PUT", body: JSON.stringify(data) }),
		delete: (id: string) =>
			fetcher(`/api/warmups/${id}`, { method: "DELETE" }),
		tick: (id: string) =>
			fetcher(`/api/warmups/${id}/tick`, { method: "POST" }),
	},
	balance: {
		get: (projectId: string) => fetcher(`/api/projects/${projectId}/balance`),
		add: (projectId: string, data: { amount: number; description?: string }) =>
			fetcher(`/api/projects/${projectId}/balance/add`, { method: "POST", body: JSON.stringify(data) }),
		set: (projectId: string, data: { balance: number }) =>
			fetcher(`/api/projects/${projectId}/balance/set`, { method: "POST", body: JSON.stringify(data) }),
		history: (projectId: string, page: number = 1, pageSize: number = 20) =>
			fetcher(`/api/projects/${projectId}/balance/history?page=${page}&page_size=${pageSize}`),
	},
	groups: {
		list: () => fetcher("/api/projects/groups"),
		create: (data: any) =>
			fetcher("/api/projects/groups", { method: "POST", body: JSON.stringify(data) }),
		update: (id: string, data: any) =>
			fetcher(`/api/projects/groups/${id}`, { method: "PUT", body: JSON.stringify(data) }),
		delete: (id: string) =>
			fetcher(`/api/projects/groups/${id}`, { method: "DELETE" }),
	},
	queue: {
		list: (project?: string, status?: string, fromDate?: string, toDate?: string, integration?: string) => {
			let path = "/api/queue/?";
			if (project) path += `project_id=${project}&`;
			if (status) path += `status=${status}&`;
			if (fromDate) path += `from_date=${encodeURIComponent(fromDate)}&`;
			if (toDate) path += `to_date=${encodeURIComponent(toDate)}`;
			if (integration) path += `integration=${encodeURIComponent(integration)}`;
			return fetcher(path);
		},
		push: (data: any) =>
			fetcher("/api/queue/push", { method: "POST", body: JSON.stringify(data) }),
		results: (data: any) =>
			fetcher("/api/queue/results", { method: "POST", body: JSON.stringify(data) }),
		clear: (projectId: string) =>
			fetcher(`/api/queue/clear?project_id=${projectId}`, { method: "POST" }),
		proklik: (data: any) =>
			fetcher("/api/queue/proklik", { method: "POST", body: JSON.stringify(data) }),
		feed: (projectId?: string, fromDate?: string, toDate?: string, integration?: string) => {
			let url = `${BASE_URL}/api/queue/feed`;
			const params = new URLSearchParams();
			if (projectId) params.set("project_id", projectId);
			if (fromDate) params.set("from_date", fromDate);
			if (toDate) params.set("to_date", toDate);
			if (integration) params.set("integration", integration);
			if (params.toString()) url += "?" + params.toString();
			return new EventSource(url);
		},
		stats: (projectId?: string, integration?: string) => {
			let path = "/api/queue/stats";
			if (projectId) path += `?project_id=${projectId}`;
			if (integration) path += `${projectId ? '&' : '?'}integration=${encodeURIComponent(integration)}`;
			return fetcher(path);
		},
		dashboardStats: () => fetcher("/api/queue/dashboard-stats"),
		dashboardServers: () => fetcher("/api/queue/dashboard-servers"),
	},
	analytics: {
		positions: () => fetcher("/api/analytics/positions"),
		clicks: (projectId?: string, suggestionMode?: string, positionThreshold?: number) => {
			let path = "/api/analytics/clicks";
			if (projectId) path += `&project_id=${projectId}`;
			if (suggestionMode) path += `&suggestion_mode=${encodeURIComponent(suggestionMode)}`;
			if (positionThreshold !== undefined && positionThreshold > 0) path += `&position_threshold=${positionThreshold}`;
			return fetcher(path);
		},
		summary: (projectId?: string, suggestionMode?: string, positionThreshold?: number) => {
			let path = "/api/analytics/summary";
			if (projectId) path += `&project_id=${projectId}`;
			if (suggestionMode) path += `&suggestion_mode=${encodeURIComponent(suggestionMode)}`;
			if (positionThreshold !== undefined && positionThreshold > 0) path += `&position_threshold=${positionThreshold}`;
			return fetcher(path);
		},
		trackingPositions: (projectId?: string) => {
		let path = "/api/analytics/tracking/positions";
		if (projectId) path += `?project_id=${projectId}`;
		return fetcher(path);
	},
	topRanges: (projectId?: string, suggestionMode?: string, positionThreshold?: number) => {
		let path = "/api/analytics/top-ranges";
		if (projectId) path += `?project_id=${projectId}`;
		if (suggestionMode) path += `&suggestion_mode=${encodeURIComponent(suggestionMode)}`;
		if (positionThreshold !== undefined && positionThreshold > 0) path += `&position_threshold=${positionThreshold}`;
		return fetcher(path);
	},
	},
	users: {
		profile: () => fetcher("/api/users/profile"),
		updateProfile: (data: any) =>
			fetcher("/api/users/profile", { method: "PUT", body: JSON.stringify(data) }),
		apiTokens: () => fetcher("/api/users/api-tokens"),
		createToken: (name: string) =>
			fetcher("/api/users/api-tokens", {
				method: "POST",
				body: JSON.stringify({ name }),
			}),
		deleteToken: (id: string) =>
			fetcher(`/api/users/api-tokens/${id}`, { method: "DELETE" }),
		messengerSettings: () => fetcher("/api/users/settings/messenger"),
		updateMessengerSettings: (data: any) =>
			fetcher("/api/users/settings/messenger", { method: "POST", body: JSON.stringify(data) }),
		externalServices: () => fetcher("/api/users/settings/external-services"),
		updateExternalServices: (data: any) =>
			fetcher("/api/users/settings/external-services", { method: "POST", body: JSON.stringify(data) }),
		stopWords: () => fetcher("/api/users/settings/stop-words"),
		updateStopWords: (words: string[]) =>
			fetcher("/api/users/settings/stop-words", { method: "POST", body: JSON.stringify({ stop_words: words }) }),
		addStopWord: (word: string) =>
			fetcher("/api/users/settings/stop-words/add", { method: "POST", body: JSON.stringify({ word }) }),
		removeStopWord: (word: string) =>
			fetcher(`/api/users/settings/stop-words/${encodeURIComponent(word)}`, { method: "DELETE" }),
		changePassword: (data: any) =>
			fetcher("/api/users/password", { method: "POST", body: JSON.stringify(data) }),
		uploadAvatar: (data: { avatar_url: string }) =>
			fetcher("/api/users/avatar", { method: "POST", body: JSON.stringify(data) }),
		deleteAvatar: () =>
			fetcher("/api/users/avatar", { method: "DELETE" }),
		getAvatar: () => fetcher("/api/users/avatar"),
	},
	notifications: {
		list: () => fetcher("/api/notifications/"),
		markRead: (id: string) =>
			fetcher(`/api/notifications/${id}/read`, { method: "POST" }),
		markAllRead: () =>
			fetcher("/api/notifications/mark-all-read", { method: "POST" }),
	},
	external: {
		getToken: () => localStorage.getItem("external_token") || "",
		header: () => ({ "X-Auth-Token": api.external.getToken() }),
	},
};
