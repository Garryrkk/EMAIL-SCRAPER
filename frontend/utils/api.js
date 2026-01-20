/**
 * Apollo Email Intelligence - API Client
 * Connects all backend endpoints with authentication
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const ACCESS_KEY = "apollo_access_token";
const REFRESH_KEY = "apollo_refresh_token";

const isBrowser = () => typeof window !== "undefined";

// Helper to extract domain from URL or string
const extractDomain = (input) => {
	if (!input) return "";
	let domain = input.trim();
	// Remove protocol
	domain = domain.replace(/^https?:\/\//i, "");
	// Remove www.
	domain = domain.replace(/^www\./i, "");
	// Remove path, query, hash
	domain = domain.split("/")[0].split("?")[0].split("#")[0];
	return domain.toLowerCase();
};

// ===================
// Token Management
// ===================

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

export const isAuthenticated = () => !!getAccessToken();

// ===================
// Request Helper
// ===================

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
		// Handle 401 - try refresh
		if (res.status === 401 && withAuth) {
			try {
				await refresh();
				// Retry with new token
				return request(path, options, withAuth);
			} catch {
				clearTokens();
				if (isBrowser()) window.location.href = "/login";
			}
		}
		const detail = payload?.detail || payload?.message || res.statusText;
		throw new Error(detail || "Request failed");
	}

	return payload;
}

// ===================
// Auth Endpoints
// ===================

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

export async function changePassword(currentPassword, newPassword) {
	return request("/auth/change-password", {
		method: "POST",
		body: JSON.stringify({
			current_password: currentPassword,
			new_password: newPassword,
		}),
	});
}

export function logout() {
	clearTokens();
	if (isBrowser()) window.location.href = "/login";
}

// ===================
// User Endpoints
// ===================

export const getProfile = () => request("/users/me");

export const updateProfile = (data) =>
	request("/users/me", {
		method: "PUT",
		body: JSON.stringify(data),
	});

export const getCredits = () => request("/users/credits");

export const getUsage = () => request("/users/usage");

// ===================
// Search Endpoints
// ===================

export const searchDomain = (domainOrOptions) => {
	const rawDomain = typeof domainOrOptions === "string" ? domainOrOptions : domainOrOptions.domain;
	const domain = extractDomain(rawDomain);
	return request("/search/domain", {
		method: "POST",	
		body: JSON.stringify({ domain }),
	});
};

export const searchPerson = (domain, firstName, lastName) =>
	request("/search/person", {
		method: "POST",
		body: JSON.stringify({
			domain,
			first_name: firstName,
			last_name: lastName,
		}),
	});

// ===================
// Email Endpoints
// ===================

export const verifyEmail = (emailOrPayload, domain) => {
	const email = typeof emailOrPayload === "object" ? emailOrPayload.email : emailOrPayload;
	const dom = typeof emailOrPayload === "object" ? emailOrPayload.domain : domain;
	return request("/emails/verify", {
		method: "POST",
		body: JSON.stringify({ email, domain: dom }),
	});
};

export const bulkVerifyEmails = (emails, domain) =>
	request(`/emails/bulk-verify?domain=${encodeURIComponent(domain)}`, {
		method: "POST",
		body: JSON.stringify(emails),
	});

export const getEmailHistory = (limit = 50, offset = 0) =>
	request(`/emails/history?limit=${limit}&offset=${offset}`);

// ===================
// Company Endpoints
// ===================

export const getCompany = (rawDomain) => {
	const domain = extractDomain(rawDomain);
	return request(`/companies/${encodeURIComponent(domain)}`);
};

export const rescanCompany = (rawDomain) => {
	const domain = extractDomain(rawDomain);
	return request(`/companies/${encodeURIComponent(domain)}/rescan`, {
		method: "POST",
	});
};

// ===================
// People Endpoints
// ===================

export const listPeople = (options = {}) => {
	const params = new URLSearchParams();
	if (options.companyId) params.set("company_id", options.companyId);
	if (options.limit) params.set("limit", options.limit);
	if (options.offset) params.set("offset", options.offset);
	const query = params.toString();
	return request(`/people${query ? `?${query}` : ""}`);
};

export const getPerson = (personId) =>
	request(`/people/${encodeURIComponent(personId)}`);

export const createPerson = (data) =>
	request("/people", {
		method: "POST",
		body: JSON.stringify({
			first_name: data.firstName,
			last_name: data.lastName,
			email: data.email,
			company_id: data.companyId,
			job_title: data.jobTitle,
			linkedin_url: data.linkedinUrl,
		}),
	});

export const deletePerson = (personId) =>
	request(`/people/${encodeURIComponent(personId)}`, {
		method: "DELETE",
	});

// ===================
// Health Check
// ===================

export const healthCheck = async () => {
	try {
		const res = await fetch(`${API_URL.replace("/api/v1", "")}/health`);
		return res.ok;
	} catch {
		return false;
	}
};

// ===================
// Export All
// ===================

const api = {
	// Auth
	signup,
	login,
	logout,
	refresh,
	changePassword,
	isAuthenticated,
	
	// Tokens
	getAccessToken,
	getRefreshToken,
	setAuthTokens,
	clearTokens,
	
	// User
	getProfile,
	updateProfile,
	getCredits,
	getUsage,
	
	// Search
	searchDomain,
	searchPerson,
	
	// Emails
	verifyEmail,
	bulkVerifyEmails,
	getEmailHistory,
	
	// Companies
	getCompany,
	rescanCompany,
	
	// People
	listPeople,
	getPerson,
	createPerson,
	deletePerson,
	
	// Health
	healthCheck,
};

export default api;
