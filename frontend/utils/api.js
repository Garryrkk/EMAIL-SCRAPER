const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const ACCESS_KEY = "apollo_access_token";
const REFRESH_KEY = "apollo_refresh_token";

const isBrowser = () => typeof window !== "undefined";

export const getAccessToken = () =>
	isBrowser() ? window.localStorage.getItem(ACCESS_KEY) : null;

export const getRefreshToken = () =>
	isBrowser() ? window.localStorage.getItem(REFRESH_KEY) : null;

export const setAuthTokens = (tokens) => {
	if (!isBrowser() || !tokens) return;
	if (tokens.access_token) {
		window.localStorage.setItem(ACCESS_KEY, tokens.access_token);
	}
	if (tokens.refresh_token) {
		window.localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
	}
};

export const clearTokens = () => {
	if (!isBrowser()) return;
	window.localStorage.removeItem(ACCESS_KEY);
	window.localStorage.removeItem(REFRESH_KEY);
};

const authHeaders = () => {
	const token = getAccessToken();
	return token ? { Authorization: `Bearer ${token}` } : {};
};

async function request(path, options = {}, withAuth = true) {
	const headers = {
		"Content-Type": "application/json",
		...(withAuth ? authHeaders() : {}),
		...(options.headers || {}),
	};

	const res = await fetch(`${API_URL}${path}`, {
		...options,
		headers,
	});

	const contentType = res.headers.get("content-type") || "";
	const payload = contentType.includes("application/json") ? await res.json() : await res.text();

	if (!res.ok) {
		const detail = payload?.detail || payload?.message || res.statusText;
		throw new Error(detail || "Request failed");
	}

	return payload;
}

export async function signup(payload) {
	const data = await request("/auth/signup", {
		method: "POST",
		body: JSON.stringify(payload),
	}, false);
	setAuthTokens(data);
	return data;
}

export async function login(payload) {
	const data = await request("/auth/login", {
		method: "POST",
		body: JSON.stringify(payload),
	}, false);
	setAuthTokens(data);
	return data;
}

export async function refresh() {
	const token = getRefreshToken();
	if (!token) throw new Error("Missing refresh token");
	const data = await request("/auth/refresh", {
		method: "POST",
		body: JSON.stringify({ refresh_token: token }),
	}, false);
	setAuthTokens(data);
	return data;
}

export const getProfile = () => request("/users/me");
export const getCredits = () => request("/users/credits");

export const searchDomain = ({ domain, firstName, lastName }) =>
	request("/search/domain", {
		method: "POST",
		body: JSON.stringify({
			domain,
			first_name: firstName || undefined,
			last_name: lastName || undefined,
		}),
	});

export const verifyEmail = ({ email, domain }) =>
	request("/emails/verify", {
		method: "POST",
		body: JSON.stringify({ email, domain }),
	});

export const bulkVerify = ({ emails, domain }) =>
	request("/emails/bulk-verify?domain=" + encodeURIComponent(domain), {
		method: "POST",
		body: JSON.stringify(emails),
	});

export const getCompany = (domain) => request(`/companies/${encodeURIComponent(domain)}`);

export const getEmailById = (id) => request(`/emails/${encodeURIComponent(id)}`);
