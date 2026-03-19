/**
 * Mentorix — Auth Module (ES Module)
 * Handles login, signup, admin login, logout, and token management.
 */

// Storage keys
export const TOKEN_KEY = "mentorix_token";
export const LEARNER_KEY = "mentorix_learner_id";
export const NAME_KEY = "mentorix_name";
export const ROLE_KEY = "mentorix_role";
export const API_BASE_KEY = "mentorix_api_base";

export function getToken() { return localStorage.getItem(TOKEN_KEY); }
export function getLearnerId() { return localStorage.getItem(LEARNER_KEY); }
export function getRole() { return localStorage.getItem(ROLE_KEY) || "student"; }

export function setAuth(token, learnerId, name, role = "student") {
  localStorage.setItem(TOKEN_KEY, token);
  if (learnerId) localStorage.setItem(LEARNER_KEY, learnerId);
  else localStorage.removeItem(LEARNER_KEY);
  localStorage.setItem(NAME_KEY, name);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEARNER_KEY);
  localStorage.removeItem(NAME_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export function getApiBase() {
  if (typeof document !== "undefined") {
    const input = document.getElementById("api-base-url") || document.getElementById("api-base-url-signup");
    if (input && input.value && input.value.trim()) return input.value.trim().replace(/\/+$/, "");
  }
  return (typeof window !== "undefined" && window.__MENTORIX_API_BASE__)
    ? window.__MENTORIX_API_BASE__
    : (typeof localStorage !== "undefined" && localStorage.getItem(API_BASE_KEY)) || "http://localhost:8000";
}

export function setApiBase(url) {
  if (url && typeof localStorage !== "undefined") localStorage.setItem(API_BASE_KEY, url);
}

/**
 * Authenticated fetch wrapper — injects Bearer token, parses JSON.
 * @param {string} path - API path (e.g. "/auth/login")
 * @param {object} options - fetch options (method, body, headers)
 * @returns {Promise<object>} parsed JSON response
 */
export async function api(path, options = {}) {
  const base = getApiBase();
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`${base}${path}`, {
    ...options,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.message || `Error ${resp.status}`);
  }
  return resp.json();
}
