/** API client for TopInjector backend. */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function headers(token?: string): HeadersInit {
	const h: HeadersInit = { "Content-Type": "application/json" };
	if (token) h["Authorization"] = `Bearer ${token}`;
	return h;
}

async function fetcher(path: string, options?: RequestInit): Promise<any> {
	const res = await fetch(`${BASE_URL}${path}`, {
		...options,
		headers: { ...headers(localStorage.getItem("token") || ""), ...options?.headers },
	});
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
	},
	projects: {
		list: () => fetcher("/api/projects/"),
		get: (id: string) => fetcher(`/api/projects/${id}`),
		create: (data: any) =>
			fetcher("/api/projects/", { method: "POST", body: JSON.stringify(data) }),
		update: (id: string, data: any) =>
			fetcher(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify(data) }),
		delete: (id: string) =>
			fetcher(`/api/projects/${id}`, { method: "DELETE" }),
		queries: (projectId: string) =>
			fetcher(`/api/projects/${projectId}/queries`),
		addQuery: (projectId: string, data: any) =>
			fetcher(`/api/projects/${projectId}/queries`, {
				method: "POST",
				body: JSON.stringify(data),
			}),
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
	},
	analytics: {
		positions: () => fetcher("/api/analytics/positions"),
		clicks: () => fetcher("/api/analytics/clicks"),
		summary: () => fetcher("/api/analytics/summary"),
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
	},
	external: {
		getToken: () => localStorage.getItem("external_token") || "",
		header: () => ({ "X-Auth-Token": api.external.getToken() }),
	},
};
