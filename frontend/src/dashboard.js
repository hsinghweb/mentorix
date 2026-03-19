/**
 * Mentorix — Dashboard Module (ES Module)
 * Handles dashboard loading, chapter navigation, and progress display.
 */
import { api, getLearnerId } from "./auth.js";
import { $, show, hide, showScreen, formatTime, formatIsoDateLabel, showLoadingSkeleton, renderBreadcrumb } from "./helpers.js";

/**
 * Load and render the learner dashboard.
 * Fetches dashboard data from API and populates the UI.
 */
export async function loadDashboard() {
  const learnerId = getLearnerId();
  if (!learnerId) return;
  showScreen("dashboard");
  showLoadingSkeleton("dashboard-chapters");
  try {
    const dash = await api(`/learning/dashboard/${learnerId}`);
    renderDashboard(dash);
  } catch (err) {
    const container = $("dashboard-chapters");
    if (container) container.innerHTML = `<div class="admin-meta">${err.message}</div>`;
  }
}

/**
 * Render dashboard data into the UI.
 * @param {object} dash - Dashboard response from API
 */
export function renderDashboard(dash) {
  // Dashboard rendering logic extracted from app.js loadDashboard()
  // This module provides the structure; full rendering delegates to app.js
  console.debug("[dashboard] render", Object.keys(dash));
}

/**
 * Navigate to a specific chapter's learning view.
 * @param {number} chapterNumber
 * @param {string} chapterTitle
 */
export async function openChapter(chapterNumber, chapterTitle) {
  const learnerId = getLearnerId();
  if (!learnerId) return;
  try {
    const data = await api(`/learning/chapter/${chapterNumber}/sections?learner_id=${learnerId}`);
    return data;
  } catch (err) {
    console.error("[dashboard] openChapter error:", err);
    throw err;
  }
}
