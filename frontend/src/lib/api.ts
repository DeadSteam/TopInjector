/** API client for TopInjector backend. */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
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
		list: (params?: { search?: string; group_id?: string; region?: string; strategy_type?: string; is_active?: boolean }) => {
			let path = "/api/projects/";
			if (params) {
				const qs = new URLSearchParams();
				if (params.search) qs.set("search", params.search);
				if (params.group_id) qs.set("group_id", params.group_id);
				if (params.region) qs.set("region", params.region);
				if (params.strategy_type) qs.set("strategy_type", params.strategy_type);
				if (params.is_active !== undefined) qs.set("is_active", String(params.is_active));
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
		list: (project?: string, status?: string) => {
			let path = "/api/queue/?";
			if (project) path += `project_id=${project}&`;
			if (status) path += `status=${status}`;
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
		feed: (projectId?: string) => {
			const url = `${BASE_URL}/api/queue/feed${projectId ? `?project_id=${projectId}` : ""}`;
			return new EventSource(url);
		},
		stats: (projectId?: string) => {
			let path = "/api/queue/stats";
			if (projectId) path += `?project_id=${projectId}`;
			return fetcher(path);
		},
	},
	analytics: {
		positions: () => fetcher("/api/analytics/positions"),
		clicks: (projectId?: string) => {
			let path = "/api/analytics/clicks";
			if (projectId) path += `?project_id=${projectId}`;
			return fetcher(path);
		},
		summary: (projectId?: string) => {
			let path = "/api/analytics/summary";
			if (projectId) path += `?project_id=${projectId}`;
			return fetcher(path);
		},
		trackingPositions: (projectId?: string) => {
		let path = "/api/analytics/tracking/positions";
		if (projectId) path += `?project_id=${projectId}`;
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
