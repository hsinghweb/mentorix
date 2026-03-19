/**
 * Mentorix — Helpers Module (ES Module)
 * Shared utility functions used across all modules.
 */

/** Query element by ID. */
export function $(id) { return document.getElementById(id); }

/** Remove the "hidden" class from an element. */
export function show(el) { if (el) el.classList.remove("hidden"); }

/** Add the "hidden" class to an element. */
export function hide(el) { if (el) el.classList.add("hidden"); }

/** Sanitize a string for safe HTML insertion. */
export function sanitizeHTML(str) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

/** Debounce a function call by `ms` milliseconds. */
export function debounce(fn, ms = 800) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}

/** Format seconds as MM:SS (e.g. 1800 → "30:00"). */
export function formatTime(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/** Format ISO date for display (e.g. "2026-03-15" → "Mar 15, 2026"). Returns "—" on null/invalid. */
export function formatIsoDateLabel(isoDate) {
  if (isoDate == null || isoDate === "") return "\u2014";
  try {
    const d = new Date(isoDate);
    if (Number.isNaN(d.getTime())) return "\u2014";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return "\u2014";
  }
}

/** Show loading skeleton placeholders. */
export function showLoadingSkeleton(containerId, count = 3) {
  const el = $(containerId);
  if (!el) return;
  el.innerHTML = Array.from({ length: count }, () =>
    `<div class="skeleton-card"><div class="skeleton-line wide"></div><div class="skeleton-line"></div></div>`
  ).join("");
}

/** Render breadcrumb navigation. */
export function renderBreadcrumb(parts) {
  const nav = $("breadcrumb-nav");
  if (!nav) return;
  nav.innerHTML = parts.map((p, i) =>
    i < parts.length - 1
      ? `<span class="breadcrumb-link" onclick="${p.action || ''}">${sanitizeHTML(p.label)}</span><span class="breadcrumb-sep">›</span>`
      : `<span class="breadcrumb-current">${sanitizeHTML(p.label)}</span>`
  ).join("");
  nav.classList.remove("hidden");
}

/** Show a specific screen by name, hiding all others. */
export function showScreen(screenName) {
  document.querySelectorAll(".screen").forEach(s => s.classList.add("hidden"));
  const screen = $(`screen-${screenName}`);
  if (screen) screen.classList.remove("hidden");
}

/** Extract chapter number from a label string (e.g. "Chapter 5" → 5). */
export function extractChapterNumber(chapterLabel) {
  if (!chapterLabel) return null;
  const match = String(chapterLabel).match(/(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}
