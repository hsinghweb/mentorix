/**
 * Mentorix — Admin Module (ES Module)
 * Handles admin dashboard, student management, agent visualization.
 */
import { api } from "./auth.js";
import { $, show, hide } from "./helpers.js";

/**
 * Load admin dashboard data — system overview + students.
 * Agent overview is lazy-loaded via IntersectionObserver when scrolled into view.
 */
export async function loadAdminDashboard() {
  const overviewEl = $("admin-system-overview");
  const summaryEl = $("admin-student-summary");
  const listEl = $("admin-student-list");
  const detailEl = $("admin-student-detail");
  const agentsEl = $("admin-agent-overview");

  if (overviewEl) overviewEl.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading system overview...</p></div>`;
  if (listEl) listEl.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading students...</p></div>`;

  try {
    const [system, students] = await Promise.all([
      api("/admin/system-overview"),
      api("/admin/students"),
    ]);
    renderAdminSystemOverview(system);
    renderAdminStudentList(students);

    // Lazy-load agent overview via IntersectionObserver
    if (agentsEl) {
      agentsEl.innerHTML = `<div class="loading-overlay"><p>Agent overview loads when scrolled into view…</p></div>`;
      const observer = new IntersectionObserver(async (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            observer.disconnect();
            agentsEl.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading agent activity...</p></div>`;
            try {
              const agents = await api("/admin/agents/overview");
              renderAdminAgentOverview(agents);
            } catch (err) {
              agentsEl.innerHTML = `<div class="admin-meta">${err.message}</div>`;
            }
          }
        }
      }, { threshold: 0.1 });
      observer.observe(agentsEl);
    }
  } catch (err) {
    if (overviewEl) overviewEl.innerHTML = `<div class="admin-meta">${err.message}</div>`;
  }
}

/**
 * Render system overview cards (environment, active runs, requests, etc.)
 */
export function renderAdminSystemOverview(data) {
  const el = $("admin-system-overview");
  if (!el) return;
  const traffic = data.traffic || {};
  const service = data.service || {};
  const infra = data.infrastructure || {};
  const req = traffic.request_metrics || {};
  el.innerHTML = `
    <div class="comparative-card"><div class="comparative-label">Environment</div><div class="comparative-value">${service.environment || "local"}</div></div>
    <div class="comparative-card"><div class="comparative-label">Active Runs</div><div class="comparative-value">${service.active_runs ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">Requests</div><div class="comparative-value">${req.requests_total ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">Redis</div><div class="comparative-value">${infra.redis?.connected ? "Connected" : "Down"}</div></div>
  `;
}

/**
 * Render the agent overview cards.
 */
export function renderAdminAgentOverview(data) {
  const el = $("admin-agent-overview");
  if (!el) return;
  const agents = data.agents || [];
  el.innerHTML = agents.map(agent => `
    <div class="comparative-card">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
        <div>
          <div class="comparative-label">${agent.title}</div>
          <div class="admin-meta">${agent.purpose}</div>
        </div>
        <span class="signal-chip ${agent.status === "working" ? "risk" : "ok"}">${agent.status}</span>
      </div>
      <div class="admin-meta" style="margin-top:10px">Hint: ${agent.status_hint || "Awaiting next trigger"}</div>
      <div class="admin-meta">Latest: ${agent.latest_decision_type || "No recent decision"}</div>
    </div>
  `).join("");
}

/**
 * Render the list of students in the admin sidebar.
 */
export function renderAdminStudentList(data) {
  const el = $("admin-student-list");
  if (!el) return;
  const students = data.students || [];
  if (!students.length) {
    el.innerHTML = `<div class="admin-meta">No students registered yet.</div>`;
    return;
  }
  el.innerHTML = students.map(s => `
    <div class="admin-student-row" onclick="loadAdminStudentDetail('${s.learner_id}')">
      <span class="admin-student-name">${s.name || s.username || "Unknown"}</span>
      <span class="admin-meta">${s.progress_status || "active"}</span>
    </div>
  `).join("");
}

/**
 * Load detailed information about a specific student.
 * @param {string} learnerId
 */
export async function loadAdminStudentDetail(learnerId) {
  const el = $("admin-student-detail");
  if (!el) return;
  el.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading student details...</p></div>`;
  try {
    const data = await api(`/admin/students/${learnerId}/detail`);
    el.innerHTML = `
      <h3>${data.name || "Student"}</h3>
      <div class="admin-meta">Mastery: ${Math.round((data.overall_mastery || 0) * 100)}%</div>
      <div class="admin-meta">Completion: ${Math.round(data.overall_completion || 0)}%</div>
    `;
  } catch (err) {
    el.innerHTML = `<div class="admin-meta">${err.message}</div>`;
  }
}
