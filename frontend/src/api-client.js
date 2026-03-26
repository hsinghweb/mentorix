/**
 * Mentorix API Client — typed request/response wrappers for backend endpoints.
 *
 * Centralizes all `fetch()` calls, adding:
 * - Automatic JWT token injection
 * - Response error handling
 * - Base URL configuration
 * - Request/response typing via JSDoc
 */

const DEFAULT_BASE_URL = 'http://localhost:8000';

/**
 * @typedef {Object} ApiConfig
 * @property {string} baseUrl
 * @property {string|null} token
 */

/** @type {ApiConfig} */
const config = {
    baseUrl: localStorage.getItem('api_base_url') || DEFAULT_BASE_URL,
    token: localStorage.getItem('access_token'),
};

/**
 * Update the API client configuration.
 * @param {Partial<ApiConfig>} updates
 */
export function configure(updates) {
    if (updates.baseUrl) config.baseUrl = updates.baseUrl;
    if (updates.token !== undefined) config.token = updates.token;
}

/**
 * Core fetch wrapper with auth, error handling, and JSON parsing.
 * @param {string} path - API path (e.g., '/learning/dashboard/123')
 * @param {RequestInit} [options={}] - Fetch options
 * @returns {Promise<any>}
 */
async function request(path, options = {}) {
    const url = `${config.baseUrl}${path}`;
    const headers = {
        'Content-Type': 'application/json',
        ...(config.token ? { Authorization: `Bearer ${config.token}` } : {}),
        ...(options.headers || {}),
    };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new ApiError(response.status, error.detail || 'Request failed', error);
    }

    if (response.status === 204) return null;
    return response.json();
}

/** Custom API error class. */
export class ApiError extends Error {
    /** @param {number} status @param {string} message @param {any} data */
    constructor(status, message, data = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

// ── Auth ────────────────────────────────────────────────────────────

/**
 * @param {string} username
 * @param {string} password
 * @returns {Promise<{access_token: string, learner_id: string}>}
 */
export async function login(username, password) {
    const data = await request('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
    });
    if (data.access_token) {
        config.token = data.access_token;
        localStorage.setItem('access_token', data.access_token);
    }
    return data;
}

/**
 * @param {Object} params
 * @returns {Promise<{access_token: string, learner_id: string}>}
 */
export async function signup(params) {
    const data = await request('/auth/signup', {
        method: 'POST',
        body: JSON.stringify(params),
    });
    if (data.access_token) {
        config.token = data.access_token;
        localStorage.setItem('access_token', data.access_token);
    }
    return data;
}

// ── Dashboard ───────────────────────────────────────────────────────

/** @param {string} learnerId @returns {Promise<Object>} */
export const getDashboard = (learnerId) =>
    request(`/learning/dashboard/${learnerId}`);

/** @param {string} learnerId @returns {Promise<Object>} */
export const getConfidenceTrend = (learnerId) =>
    request(`/learning/confidence-trend/${learnerId}`);

/** @param {string} learnerId @returns {Promise<Object>} */
export const getDecisions = (learnerId) =>
    request(`/learning/decisions/${learnerId}`);

/** @param {string} learnerId @returns {Promise<Object>} */
export const getPlanHistory = (learnerId) =>
    request(`/learning/plan-history/${learnerId}`);

// ── Content ─────────────────────────────────────────────────────────

/** @param {Object} payload @returns {Promise<Object>} */
export const getContent = (payload) =>
    request('/learning/content', { method: 'POST', body: JSON.stringify(payload) });

/** @param {Object} payload @returns {Promise<Object>} */
export const getSectionContent = (payload) =>
    request('/learning/content/section', { method: 'POST', body: JSON.stringify(payload) });

/** @param {Object} payload @returns {Promise<Object>} */
export const completeReading = (payload) =>
    request('/learning/reading/complete', { method: 'POST', body: JSON.stringify(payload) });

// ── Testing ─────────────────────────────────────────────────────────

/** @param {Object} payload @returns {Promise<Object>} */
export const generateTest = (payload) =>
    request('/learning/test/generate', { method: 'POST', body: JSON.stringify(payload) });

/** @param {Object} payload @returns {Promise<Object>} */
export const submitTest = (payload) =>
    request('/learning/test/submit', { method: 'POST', body: JSON.stringify(payload) });

/** @param {Object} payload @returns {Promise<Object>} */
export const explainQuestion = (payload) =>
    request('/learning/test/question/explain', { method: 'POST', body: JSON.stringify(payload) });

/** @param {Object} payload @returns {Promise<Object>} */
export const generateSectionTest = (payload) =>
    request('/learning/test/section/generate', { method: 'POST', body: JSON.stringify(payload) });

// ── Week & Tasks ────────────────────────────────────────────────────

/** @param {Object} payload @returns {Promise<Object>} */
export const advanceWeek = (payload) =>
    request('/learning/week/advance', { method: 'POST', body: JSON.stringify(payload) });

/** @param {string} learnerId @returns {Promise<Object>} */
export const getTasks = (learnerId) =>
    request(`/onboarding/tasks/${learnerId}`);

/** @param {string} taskId @returns {Promise<Object>} */
export const completeTask = (taskId) =>
    request(`/onboarding/tasks/${taskId}/complete`, { method: 'POST' });

// ── Onboarding ──────────────────────────────────────────────────────

/** @param {Object} payload @returns {Promise<Object>} */
export const startOnboarding = (payload) =>
    request('/onboarding/start', { method: 'POST', body: JSON.stringify(payload) });

/** @param {Object} payload @returns {Promise<Object>} */
export const submitDiagnostic = (payload) =>
    request('/onboarding/submit', { method: 'POST', body: JSON.stringify(payload) });

/** @param {string} learnerId @returns {Promise<Object>} */
export const getPlan = (learnerId) =>
    request(`/onboarding/plan/${learnerId}`);

// ── Admin ───────────────────────────────────────────────────────────

/** @param {string} learnerId @returns {Promise<Object>} */
export const getLearnerMetrics = (learnerId) =>
    request(`/onboarding/learning-metrics/${learnerId}`);

/** @param {string} learnerId @returns {Promise<Object>} */
export const getComparativeAnalytics = (learnerId) =>
    request(`/onboarding/comparative-analytics/${learnerId}`);

// ── Analytics ───────────────────────────────────────────────────────

/** @returns {Promise<Object>} */
export const getCohortOutcomes = () =>
    request('/analytics/outcomes');

/** @param {string} learnerId @returns {Promise<Object>} */
export const getLearnerOutcome = (learnerId) =>
    request(`/analytics/outcomes/${learnerId}`);

/** @returns {Promise<Object>} */
export const getExperiments = () =>
    request('/analytics/experiments');
