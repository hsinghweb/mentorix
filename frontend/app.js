// API and auth storage keys
const TOKEN_KEY = "mentorix_token";
const LEARNER_KEY = "mentorix_learner_id";
const NAME_KEY = "mentorix_name";
const ROLE_KEY = "mentorix_role";
const API_BASE_KEY = "mentorix_api_base";

function getApiBase() {
  if (typeof document !== "undefined") {
    const input = document.getElementById("api-base-url") || document.getElementById("api-base-url-signup");
    if (input && input.value && input.value.trim()) return input.value.trim().replace(/\/+$/, "");
  }
  return (typeof window !== "undefined" && window.__MENTORIX_API_BASE__)
    ? window.__MENTORIX_API_BASE__
    : (typeof localStorage !== "undefined" && localStorage.getItem(API_BASE_KEY)) || "http://localhost:8000";
}

function setApiBase(url) {
  if (url && typeof localStorage !== "undefined") localStorage.setItem(API_BASE_KEY, url);
}

let diagnosticData = null;     // { attempt_id, questions, answer_key, signup_draft_id }
let diagnosticTimer = null;
let diagnosticSeconds = 1800;  // 30 minutes
let readingTimer = null;
let readingSeconds = 0;
let readingTaskId = null;
let readingChapterNumber = null;
let testTimer = null;
let testSeconds = 1200;        // 20 minutes
let currentTestData = null;    // { test_id, questions, chapter, chapter_number }

// -- HELPERS -----------------------------------------------------------------
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function getLearnerId() { return localStorage.getItem(LEARNER_KEY); }
function getRole() { return localStorage.getItem(ROLE_KEY) || "student"; }
function setAuth(token, learnerId, name, role = "student") {
  localStorage.setItem(TOKEN_KEY, token);
  if (learnerId) localStorage.setItem(LEARNER_KEY, learnerId);
  else localStorage.removeItem(LEARNER_KEY);
  localStorage.setItem(NAME_KEY, name);
  localStorage.setItem(ROLE_KEY, role);
}
function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEARNER_KEY);
  localStorage.removeItem(NAME_KEY);
  localStorage.removeItem(ROLE_KEY);
}

async function api(path, options = {}) {
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

function $(id) { return document.getElementById(id); }
function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }
function showAuthPanel(panelId) {
  ["panel-login", "panel-admin-login", "panel-signup", "panel-diagnostic", "panel-result"].forEach(id => {
    const el = $(id);
    if (el) el.classList.toggle("hidden", id !== panelId);
  });
}

function renderKaTeX(container) {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(container, {
      delimiters: [
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
        { left: "$$", right: "$$", display: true },
      ],
      throwOnError: false,
    });
  }
}

function normalizeMathDelimiters(text) {
  if (!text) return "";
  let s = String(text)
    .replace(/\\\\\(/g, "\\(")
    .replace(/\\\\\)/g, "\\)")
    .replace(/\\\\\[/g, "\\[")
    .replace(/\\\\\]/g, "\\]")
    // Heuristic fallback: wrap plain parenthesized LaTeX commands so KaTeX can render.
    .replace(/\(\s*(\\[A-Za-z]+[^()\n]{0,220})\s*\)/g, "\\($1\\)")
    .replace(/\r\n/g, "\n")
    .replace(/[\u200B-\u200D\uFEFF]/g, "");

  // Fix malformed inline closers: \(\sqrt{2} \\) -> \(\sqrt{2}\)
  s = s.replace(/\\\(([\s\S]*?)\\\\\)/g, "\\($1\\)");

  // Fix bare LaTeX fragments that end with closer but are not wrapped:
  // \sqrt{2}\) or \sqrt{2}\\) -> \(\sqrt{2}\)
  s = s.replace(
    /(^|[\s,;:([{\-])((?:\\[A-Za-z]+(?:\{[^{}]*\}|[A-Za-z0-9._^+-])*)+)\\\)/g,
    (m, p1, p2, offset, full) => {
      const at = Number(offset || 0) + String(p1 || "").length;
      if (at >= 2 && String(full).slice(at - 2, at) === "\\(") return m;
      return `${p1}\\(${p2.replace(/\\\)$/, "")}\\)`;
    }
  );

  // Fix orphan opener for single symbol: "\(p is ..." -> "\(p\) is ..."
  s = s.replace(
    /\\\(\s*([A-Za-z0-9][A-Za-z0-9_^{}]*)\s+([A-Za-z])/g,
    "\\($1\\) $2"
  );

  // Normalize accidental duplicated trailing slashes inside inline math.
  s = s.replace(/\\\(([^)]*?)\\\\\s*\\\)/g, "\\($1\\)");

  // Defensive cleanup: auto-close unmatched inline math openers "\(".
  // This prevents KaTeX from rendering the rest of the line as an error block.
  let inlineOpenBalance = 0;
  for (let i = 0; i < s.length - 1; i++) {
    if (s[i] === "\\" && s[i + 1] === "(") {
      inlineOpenBalance += 1;
      i += 1;
      continue;
    }
    if (s[i] === "\\" && s[i + 1] === ")") {
      if (inlineOpenBalance > 0) inlineOpenBalance -= 1;
      i += 1;
    }
  }
  if (inlineOpenBalance > 0) {
    s += "\\)".repeat(inlineOpenBalance);
  }

  // Defensive cleanup for unmatched display openers "\[".
  let displayOpenBalance = 0;
  for (let i = 0; i < s.length - 1; i++) {
    if (s[i] === "\\" && s[i + 1] === "[") {
      displayOpenBalance += 1;
      i += 1;
      continue;
    }
    if (s[i] === "\\" && s[i + 1] === "]") {
      if (displayOpenBalance > 0) displayOpenBalance -= 1;
      i += 1;
    }
  }
  if (displayOpenBalance > 0) {
    s += "\\]".repeat(displayOpenBalance);
  }

  // Defensive cleanup for unbalanced $$ display delimiters.
  const doubleDollarMatches = s.match(/\$\$/g);
  if (doubleDollarMatches && doubleDollarMatches.length % 2 !== 0) {
    s += "$$";
  }
  return s;
}

function protectMathBlocks(text) {
  const source = normalizeMathDelimiters(text);
  const tokens = [];
  let idx = 0;
  const sanitizeMathToken = (token) => {
    let t = String(token || "");
    if (t.startsWith("\\(") && t.endsWith("\\)")) {
      let inner = t.slice(2, -2).trim();
      // Repair malformed inline math like: \(\sqrt{2} \\)
      inner = inner.replace(/\\\\\s*$/, "").trim();
      return `\\(${inner}\\)`;
    }
    if (t.startsWith("\\[") && t.endsWith("\\]")) {
      let inner = t.slice(2, -2).trim();
      inner = inner.replace(/\\\\\s*$/, "").trim();
      return `\\[${inner}\\]`;
    }
    return t;
  };
  const put = (m) => {
    const key = `@@MATH_BLOCK_${idx++}@@`;
    tokens.push([key, sanitizeMathToken(m)]);
    return key;
  };
  const masked = source
    .replace(/\\\([\s\S]*?\\\)/g, put)
    .replace(/\\\[[\s\S]*?\\\]/g, put)
    .replace(/\$\$[\s\S]*?\$\$/g, put)
    .replace(/\$[^$\n]+\$/g, put);
  return {
    masked,
    restore: (html) => {
      let out = String(html || "");
      for (const [key, value] of tokens) out = out.split(key).join(value);
      return out;
    },
  };
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function mdToHtml(md) {
  const { masked, restore } = protectMathBlocks(md);
  if (!masked) return "";
  if (typeof marked !== "undefined" && typeof marked.parse === "function") {
    try {
      return restore(marked.parse(masked, { breaks: true, gfm: true }));
    } catch (err) {
      console.warn("Markdown parse failed, using safe fallback:", err);
    }
  }
  return `<pre style="white-space:pre-wrap;color:var(--text-primary)">${restore(masked
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>"))}</pre>`;
}

function mdInlineToHtml(md) {
  const { masked, restore } = protectMathBlocks(md);
  if (!masked) return "";
  if (typeof marked !== "undefined" && typeof marked.parseInline === "function") {
    return restore(marked.parseInline(masked));
  }
  return restore(masked
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;"));
}

function extractChapterNumber(chapterLabel) {
  if (!chapterLabel) return null;
  const match = String(chapterLabel).match(/(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

async function resolveCurrentWeekTask(taskType, chapterNumber, sectionId = null) {
  const learnerId = getLearnerId();
  if (!learnerId) return null;
  try {
    const dash = await api(`/learning/dashboard/${learnerId}`);
    const tasks = dash.current_week_tasks || [];
    const found = tasks.find(t => {
      if (t.task_type !== taskType) return false;
      const taskChapter = extractChapterNumber(t.chapter);
      if (taskChapter !== chapterNumber) return false;
      if (sectionId) return (t.section_id || "") === sectionId;
      return !t.section_id;
    });
    if (!found) return null;
    return {
      task_id: found.task_id || null,
      min_seconds: Number.isFinite(parseInt(found.min_seconds, 10)) ? parseInt(found.min_seconds, 10) : null,
    };
  } catch (err) {
    console.warn("Task id resolution failed:", err);
    return null;
  }
}

function parseMinSecondsFromReason(reasonText) {
  const text = String(reasonText || "");
  const m = text.match(/at least\s+(\d+)\s+minute/i);
  if (!m) return null;
  const mins = parseInt(m[1], 10);
  if (!Number.isFinite(mins) || mins <= 0) return null;
  return mins * 60;
}

function showFinalTestBlockedModal(chapterNumber, reasonCode, pendingTasks = []) {
  const existing = document.getElementById("final-test-blocked-overlay");
  if (existing) existing.remove();
  const overlay = document.createElement("div");
  overlay.id = "final-test-blocked-overlay";
  overlay.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.72);z-index:1200;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);";
  const pendingHtml = (pendingTasks || []).slice(0, 8).map(t => `<li style=\"margin:4px 0\">${mdInlineToHtml(t)}</li>`).join("");
  const reasonText = reasonCode === "pending_subsection_tasks"
    ? "Complete subsection reading and subsection tests first."
    : "Prerequisites are not complete yet.";
  overlay.innerHTML = `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);max-width:640px;width:92%;padding:24px;box-shadow:var(--shadow)">
      <h3 style="margin-bottom:8px">Final Test Locked • Chapter ${chapterNumber}</h3>
      <p style="color:var(--text-secondary);margin-bottom:12px">${reasonText}</p>
      ${pendingHtml ? `<div style="background:var(--bg-elevated);border:1px solid var(--border);border-radius:10px;padding:10px 12px;max-height:200px;overflow:auto"><div style="font-weight:600;margin-bottom:6px">Pending tasks</div><ul style="margin-left:18px">${pendingHtml}</ul></div>` : ""}
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:14px">
        <button class="btn btn-outline" onclick="document.getElementById('final-test-blocked-overlay').remove()">Close</button>
        <button class="btn btn-primary" onclick="document.getElementById('final-test-blocked-overlay').remove();showScreen('dashboard');loadDashboard();">Go to Week Tasks</button>
      </div>
    </div>
  `;
  overlay.addEventListener("click", e => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}


// -- INITIALIZATION ----------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initWeeksDropdown();
  bindEvents();
  checkAuthState();
});

function initWeeksDropdown() {
  const sel = $("signup-weeks");
  if (sel) {
    for (let w = 14; w <= 28; w++) {
      const opt = document.createElement("option");
      opt.value = w;
      opt.textContent = `${w} weeks`;
      sel.appendChild(opt);
    }
  }
  const savedBase = typeof localStorage !== "undefined" && localStorage.getItem(API_BASE_KEY);
  if (savedBase) {
    const inp = $("api-base-url");
    const inpAdmin = $("api-base-url-admin");
    const inp2 = $("api-base-url-signup");
    if (inp) inp.value = savedBase;
    if (inpAdmin) inpAdmin.value = savedBase;
    if (inp2) inp2.value = savedBase;
  }
}

function bindEvents() {
  // Auth
  $("form-login").addEventListener("submit", handleLogin);
  $("form-admin-login").addEventListener("submit", handleAdminLogin);
  $("form-signup").addEventListener("submit", handleSignup);
  $("link-to-signup").addEventListener("click", e => { e.preventDefault(); showAuthPanel("panel-signup"); });
  $("link-to-login").addEventListener("click", e => { e.preventDefault(); showAuthPanel("panel-login"); });
  $("link-to-admin").addEventListener("click", e => { e.preventDefault(); showAuthPanel("panel-admin-login"); });
  $("link-admin-to-login").addEventListener("click", e => { e.preventDefault(); showAuthPanel("panel-login"); });
  $("btn-logout").addEventListener("click", handleLogout);
  if ($("btn-admin-overview")) $("btn-admin-overview").addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  if ($("btn-admin-students")) $("btn-admin-students").addEventListener("click", () => $("admin-student-list")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  if ($("btn-admin-agents")) $("btn-admin-agents").addEventListener("click", () => $("admin-agent-overview")?.scrollIntoView({ behavior: "smooth", block: "start" }));

  // Diagnostic
  $("btn-submit-test").addEventListener("click", handleSubmitDiagnostic);

  // Result
  $("btn-go-dashboard").addEventListener("click", () => { hide($("auth-gate")); show($("app-main")); loadDashboard(); });

  // Reading & Test
  $("btn-back-from-reading").addEventListener("click", backToDashboard);
  $("btn-back-from-test").addEventListener("click", backToDashboard);
  $("btn-submit-chapter-test").addEventListener("click", handleSubmitChapterTest);

  // Practice screen
  if ($("btn-back-from-practice")) $("btn-back-from-practice").addEventListener("click", backToDashboard);
  if ($("btn-check-practice")) $("btn-check-practice").addEventListener("click", checkPractice);
  if ($("btn-close-source")) $("btn-close-source").addEventListener("click", closeSourceOverlay);
  if ($("source-overlay")) $("source-overlay").addEventListener("click", e => {
    if (e.target === $("source-overlay")) closeSourceOverlay();
  });
}

function checkAuthState() {
  if (!getToken()) return;
  const role = getRole();
  if (role === "admin") {
    hide($("auth-gate"));
    show($("app-main"));
    configureNavForRole("admin", localStorage.getItem(NAME_KEY) || "Admin");
    loadAdminDashboard();
    return;
  }
  if (getLearnerId()) {
    hide($("auth-gate"));
    show($("app-main"));
    configureNavForRole("student", localStorage.getItem(NAME_KEY) || "Student");
    loadDashboard();
  }
}

function configureNavForRole(role, displayName) {
  $("nav-student-name").textContent = displayName || (role === "admin" ? "Admin" : "Student");
  const badge = $("nav-role-badge");
  const adminNav = $("admin-nav");
  if (badge) {
    badge.textContent = role === "admin" ? "Admin" : "Student";
    badge.classList.remove("hidden");
  }
  if (adminNav) adminNav.classList.toggle("hidden", role !== "admin");
}


// -- AUTH ---------------------------------------------------------------------
async function handleLogin(e) {
  e.preventDefault();
  const errEl = $("login-error");
  hide(errEl);

  try {
    const base = getApiBase();
    const data = await api("/auth/login", {
      method: "POST",
      body: {
        username: $("login-username").value.trim(),
        password: $("login-password").value,
      },
    });
    setApiBase(base);
    setAuth(data.token, data.learner_id, data.name, data.role || "student");
    hide($("auth-gate"));
    show($("app-main"));
    configureNavForRole(data.role || "student", data.name);
    loadDashboard();
  } catch (err) {
    errEl.textContent = err.message;
    show(errEl);
  }
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const errEl = $("admin-login-error");
  hide(errEl);

  try {
    const adminBase = $("api-base-url-admin")?.value?.trim();
    if (adminBase) setApiBase(adminBase.replace(/\/+$/, ""));
    const data = await api("/auth/admin-login", {
      method: "POST",
      body: {
        username: $("admin-username").value.trim(),
        password: $("admin-password").value,
      },
    });
    setAuth(data.token, null, data.name || data.username || "Admin", data.role || "admin");
    hide($("auth-gate"));
    show($("app-main"));
    configureNavForRole("admin", data.name || data.username || "Admin");
    loadAdminDashboard();
  } catch (err) {
    errEl.textContent = err.message;
    show(errEl);
  }
}

async function handleSignup(e) {
  e.preventDefault();
  const errEl = $("signup-error");
  hide(errEl);

  try {
    setApiBase(getApiBase());
    // Step 1: Start signup
    const draft = await api("/auth/start-signup", {
      method: "POST",
      body: {
        username: $("signup-username").value.trim(),
        password: $("signup-password").value,
        name: $("signup-name").value.trim(),
        date_of_birth: $("signup-dob").value,
        student_email: $("signup-email").value.trim(),
        selected_timeline_weeks: parseInt($("signup-weeks").value),
        math_9_percent: parseInt($("signup-math9").value),
      },
    });

    // Step 2: Get diagnostic questions
    const diagResp = await api("/onboarding/diagnostic-questions", {
      method: "POST",
      body: { signup_draft_id: draft.signup_draft_id },
    });

    diagnosticData = {
      attempt_id: diagResp.diagnostic_attempt_id,
      signup_draft_id: draft.signup_draft_id,
      questions: diagResp.questions,
    };

    // Show diagnostic test
    hide($("panel-signup"));
    show($("panel-diagnostic"));
    renderDiagnosticQuestions(diagResp.questions);
    startDiagnosticTimer();
  } catch (err) {
    errEl.textContent = err.message;
    show(errEl);
  }
}

function handleLogout() {
  clearAuth();
  if (diagnosticTimer) clearInterval(diagnosticTimer);
  if (readingTimer) clearInterval(readingTimer);
  if (testTimer) clearInterval(testTimer);
  hide($("app-main"));
  show($("auth-gate"));
  showAuthPanel("panel-login");
}


// -- DIAGNOSTIC --------------------------------------------------------------
function renderDiagnosticQuestions(questions) {
  const container = $("test-questions");
  container.innerHTML = "";

  questions.forEach((q, i) => {
    const card = document.createElement("div");
    card.className = "question-card";
    card.id = `diag-q-${q.question_id}`;

    card.innerHTML = `
            <div class="question-number">Question ${i + 1} of ${questions.length}</div>
            <div class="question-prompt">${q.prompt}</div>
            <div class="question-options">
                ${q.options.map((opt, oi) => `
                    <label class="option-label" data-qid="${q.question_id}" data-idx="${oi}">
                        <input type="radio" name="diag_${q.question_id}" value="${oi}">
                        <span class="option-indicator"></span>
                        <span>${opt}</span>
                    </label>
                `).join("")}
            </div>
        `;
    container.appendChild(card);
  });

  // Bind option clicks
  container.querySelectorAll(".option-label").forEach(label => {
    label.addEventListener("click", () => {
      const qid = label.dataset.qid;
      // Remove previous selection for this question
      container.querySelectorAll(`[data-qid="${qid}"]`).forEach(l => l.classList.remove("selected"));
      label.classList.add("selected");
      label.querySelector("input").checked = true;

      // Update card state
      const card = $(`diag-q-${qid}`);
      if (card) card.classList.add("answered");

      updateDiagnosticProgress();
    });
  });

  renderKaTeX(container);
}

function updateDiagnosticProgress() {
  const answered = document.querySelectorAll(".question-card.answered").length;
  $("test-answered").textContent = answered;
  $("btn-submit-test").disabled = answered === 0;
}

function startDiagnosticTimer() {
  diagnosticSeconds = 1800;
  const timerEl = $("test-timer");
  timerEl.textContent = formatTime(diagnosticSeconds);

  diagnosticTimer = setInterval(() => {
    diagnosticSeconds--;
    timerEl.textContent = formatTime(diagnosticSeconds);
    if (diagnosticSeconds <= 300) timerEl.classList.add("danger");
    if (diagnosticSeconds <= 0) {
      clearInterval(diagnosticTimer);
      handleSubmitDiagnostic();
    }
  }, 1000);
}

async function handleSubmitDiagnostic() {
  if (diagnosticTimer) clearInterval(diagnosticTimer);
  $("btn-submit-test").disabled = true;
  $("btn-submit-test").textContent = "Submitting...";

  // Collect answers
  const answers = [];
  diagnosticData.questions.forEach(q => {
    const selected = document.querySelector(`input[name="diag_${q.question_id}"]:checked`);
    if (selected) {
      const idx = parseInt(selected.value);
      answers.push({
        question_id: q.question_id,
        answer: q.options[idx],
      });
    }
  });

  try {
    const result = await api("/onboarding/submit", {
      method: "POST",
      body: {
        signup_draft_id: diagnosticData.signup_draft_id,
        diagnostic_attempt_id: diagnosticData.attempt_id,
        answers: answers,
        time_spent_minutes: Math.ceil((1800 - diagnosticSeconds) / 60),
      },
    });

    // Save auth if token returned
    if (result.token) {
      setAuth(result.token, result.learner_id, localStorage.getItem(NAME_KEY) || $("signup-name").value);
    }

    // Show result
    hide($("panel-diagnostic"));
    show($("panel-result"));
    renderResult(result);
  } catch (err) {
    $("btn-submit-test").disabled = false;
    $("btn-submit-test").textContent = "Submit Test";
    alert("Error submitting test: " + err.message);
  }
}

function renderResult(result) {
  const container = $("result-content");
  const score = result.score;
  const scorePercent = (score * 100).toFixed(0);
  const correct = result.correct_out_of_total || `${Math.round(score * 25)}/25`;

  let chaptersHtml = "";
  if (result.chapter_scores) {
    chaptersHtml = `<div class="result-chapters">`;
    for (const [ch, sc] of Object.entries(result.chapter_scores)) {
      const cls = sc >= 0.6 ? "strong" : "weak";
      chaptersHtml += `<div class="result-ch-badge ${cls}">${ch}: ${(sc * 100).toFixed(0)}%</div>`;
    }
    chaptersHtml += `</div>`;
  }

  container.innerHTML = `
        <div class="result-score-card">
            <div class="result-score-big">${scorePercent}%</div>
            <div class="result-score-label">${correct} correct</div>
        </div>
        <div class="result-plan-note">
            You chose <strong>${result.selected_timeline_weeks} weeks</strong>.
            Based on your performance, we suggest <strong>${result.recommended_timeline_weeks} weeks</strong>.
            ${result.timeline_recommendation_note || ""}
        </div>
        ${chaptersHtml}
    `;
  renderKaTeX(container);
}


// -- DASHBOARD ---------------------------------------------------------------
async function loadDashboard() {
  showScreen("dashboard");
  const learnerId = getLearnerId();
  configureNavForRole("student", localStorage.getItem(NAME_KEY) || "Student");

  try {
    const data = await api(`/learning/dashboard/${learnerId}`);
    renderDashboard(data);
    await loadComparativeAnalytics(learnerId);
  } catch (err) {
    console.error("Dashboard load failed:", err);
    // Show a minimal dashboard if the learning endpoint fails
    try {
      // Try onboarding endpoint as fallback
      renderDashboardFallback();
      renderComparativeAnalyticsFallback("Comparative analytics unavailable");
    } catch (e2) {
      $("profile-card").innerHTML = `<div class="profile-stat"><div class="stat-value">Error</div><div class="stat-label">${err.message}</div></div>`;
    }
  }
}

function renderDashboard(data) {
  // Profile card
  $("profile-card").innerHTML = `
        <div class="profile-stat">
            <div class="stat-value">Student</div>
            <div class="stat-label">${data.student_name}</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">W${data.current_week}</div>
            <div class="stat-label">${data.current_week_label || "Current Week"}</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">${data.overall_completion_percent.toFixed(0)}%</div>
            <div class="stat-label">Completed</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">${data.overall_mastery_percent.toFixed(0)}%</div>
            <div class="stat-label">Mastery</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">${data.diagnostic_score !== null ? (data.diagnostic_score * 100).toFixed(0) + "%" : "—"}</div>
            <div class="stat-label">Diagnostic <span class="help-tip" title="Baseline onboarding assessment score used to personalize your plan. This is not your weekly performance score.">?</span></div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">${data.selected_weeks || "—"}/${data.suggested_weeks || "—"}</div>
            <div class="stat-label">Chosen / Suggested Wks <span class="help-tip" title="Chosen weeks are your preferred timeline. Suggested weeks are adaptive and can increase or decrease with your consistency and scores.">?</span></div>
        </div>
    `;

  // Current week tasks
  renderTasks(data.current_week_tasks, data.current_week, data.current_week_label);

  // Completion status
  $("completion-bar").querySelector("span").style.width = `${data.overall_completion_percent}%`;
  $("completion-label").textContent = `${data.overall_completion_percent.toFixed(0)}% Complete`;
  renderChapters(data.chapter_status);

  // Confidence
  renderConfidence(data.chapter_confidence);
  renderConfidenceTrend(data.learner_id);

  // Plan
  renderPlan(data.rough_plan, data.current_week);
  renderPlanHistory(data.learner_id);

  // Revision
  if (data.revision_queue && data.revision_queue.length > 0) {
    show($("section-revision"));
    renderRevision(data.revision_queue);
  } else {
    hide($("section-revision"));
  }

  // Check if week is complete (all tasks done) ? show advance button
  checkWeekComplete(data.current_week_tasks, data.learner_id);
}

function renderDashboardFallback() {
  $("profile-card").innerHTML = `
        <div class="profile-stat">
            <div class="stat-value">Student</div>
            <div class="stat-label">${localStorage.getItem(NAME_KEY) || "Student"}</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">—</div>
            <div class="stat-label">Loading...</div>
        </div>
    `;
}

async function loadComparativeAnalytics(learnerId) {
  try {
    const data = await api(`/onboarding/comparative-analytics/${learnerId}`);
    renderComparativeAnalytics(data);
  } catch (err) {
    console.warn("Comparative analytics load failed:", err);
    renderComparativeAnalyticsFallback("Comparative analytics not available yet.");
  }
}

function renderComparativeAnalytics(data) {
  const summary = $("comparative-summary");
  const metrics = $("comparative-metrics");
  const signals = $("comparative-signals");
  if (!summary || !metrics || !signals) return;

  const ind = data.individual || {};
  const cmp = data.comparative || {};
  const avg = cmp.average_vs_cohort || {};
  const cluster = cmp.similar_learner_cluster || {};
  const hooks = data.hooks || {};
  const ew = hooks.early_warning_signals || {};
  const anonymized = !!data.anonymized;

  summary.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap">
      <div><strong>Cohort size:</strong> ${data.cohort_size ?? 0}</div>
      <div><strong>Privacy mode:</strong> ${anonymized ? "Anonymized metrics enabled" : "Limited (cohort too small)"}</div>
      <div><strong>Adaptive hint:</strong> ${hooks.adaptive_difficulty_hint || "maintain"}</div>
    </div>
  `;

  const percentile = cmp.percentile_ranking;
  const learnerScore = Number(ind.topic_mastery_score || 0);
  const completion = Number(ind.completion_rate_percent || 0);
  const velocity = Number(ind.learning_velocity || 0);
  const trend = Number((cmp.trend_over_time || {}).improvement_trend || ind.improvement_trend || 0);
  metrics.innerHTML = `
    <div class="comparative-card">
      <div class="comparative-label">Mastery Score</div>
      <div class="comparative-value">${(learnerScore * 100).toFixed(1)}%</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Percentile Rank <span class="help-tip" title="Your standing compared to the cohort. Higher percentile means you are performing better than more learners.">?</span></div>
      <div class="comparative-value">${percentile === null || percentile === undefined ? "N/A" : `${Number(percentile).toFixed(1)}%`}</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Vs Cohort Delta <span class="help-tip" title="Difference between your mastery score and the cohort average. Positive means above average; negative means below average.">?</span></div>
      <div class="comparative-value">${avg.delta === null || avg.delta === undefined ? "N/A" : `${(Number(avg.delta) * 100).toFixed(1)}%`}</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Completion Rate</div>
      <div class="comparative-value">${completion.toFixed(1)}%</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Learning Velocity <span class="help-tip" title="How quickly you complete mastery milestones over recent activity windows. Higher means faster progression.">?</span></div>
      <div class="comparative-value">${velocity.toFixed(2)}</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Improvement Trend</div>
      <div class="comparative-value">${trend >= 0 ? "+" : ""}${(trend * 100).toFixed(1)}%</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Similar Cluster</div>
      <div class="comparative-value">${cluster.cluster_size ?? "N/A"}</div>
    </div>
  `;

  const signalRows = [
    ["Low Mastery", !!ew.low_mastery],
    ["High Timeline Drift", !!ew.timeline_drift_high],
    ["Below Cohort Avg", !!ew.below_cohort_average],
    ["Repeated Weak Performance", !!ew.repeated_weak_performance],
  ];
  signals.innerHTML = signalRows.map(([label, risk]) => `
    <div class="comparative-card">
      <div class="comparative-label">${label}</div>
      <span class="signal-chip ${risk ? "risk" : "ok"}">${risk ? "Attention" : "Stable"}</span>
    </div>
  `).join("");
}

function renderComparativeAnalyticsFallback(message) {
  const summary = $("comparative-summary");
  const metrics = $("comparative-metrics");
  const signals = $("comparative-signals");
  if (!summary || !metrics || !signals) return;
  summary.innerHTML = `<div style="color:var(--text-muted)">${message || "Comparative analytics unavailable."}</div>`;
  metrics.innerHTML = "";
  signals.innerHTML = "";
}

function renderTasks(tasks, weekNumber, weekLabel = null) {
  const container = $("current-tasks");
  $("section-tasks").querySelector(".section-title").textContent = weekLabel
    ? `${weekLabel} Tasks`
    : `Week ${weekNumber} Tasks`;

  if (!tasks || tasks.length === 0) {
    container.innerHTML = `<div class="loading-overlay"><p>No tasks yet. Complete onboarding to get started!</p></div>`;
    return;
  }

  const hasScheduledDay = tasks.some(t => !!t.scheduled_day);
  if (hasScheduledDay) {
    const grouped = {};
    tasks.forEach(t => {
      const key = t.scheduled_day
        ? new Date(t.scheduled_day).toLocaleDateString(undefined, { weekday: "short" })
        : "Unscheduled";
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(t);
    });
    container.innerHTML = Object.entries(grouped).map(([day, dayTasks]) => `
      <div style="margin-bottom:14px">
        <div style="font-weight:700;color:var(--text-primary);margin-bottom:8px">${day}</div>
        ${dayTasks.map(t => {
          const isChapterLevel = t.chapter_level;
          const icon = t.task_type === "read" ? "Read" : (isChapterLevel ? "Final" : "Quiz");
          const statusCls = t.status;
          const statusLabel = t.status.replace(/_/g, " ");
          const sectionAttr = t.section_id ? `data-section-id="${t.section_id}"` : "";
          const chapterLevelAttr = isChapterLevel ? 'data-chapter-level="true"' : "";
          return `
            <div class="task-card ${statusCls}" data-task-id="${t.task_id}" data-type="${t.task_type}" data-chapter="${t.chapter}" ${sectionAttr} ${chapterLevelAttr} style="cursor:pointer;margin-bottom:8px">
              <div class="task-icon">${icon}</div>
              <div class="task-info">
                <div class="task-title">${t.title}</div>
                <div class="task-meta">${t.chapter} • ${t.task_type.toUpperCase()}${t.section_id ? " • §" + t.section_id : isChapterLevel ? " • FINAL" : ""}</div>
              </div>
              <div class="task-status-badge ${statusCls}">${statusLabel}</div>
            </div>`;
        }).join("")}
      </div>
    `).join("");
    bindTaskCardClicks(container);
    return;
  }

  container.innerHTML = tasks.map(t => {
    const isChapterLevel = t.chapter_level;
    const icon = t.task_type === "read" ? "Read" : (isChapterLevel ? "Final" : "Quiz");
    const statusCls = t.status;
    const statusLabel = t.status.replace(/_/g, " ");
    const sectionAttr = t.section_id ? `data-section-id="${t.section_id}"` : "";
    const chapterLevelAttr = isChapterLevel ? 'data-chapter-level="true"' : "";
    return `
            <div class="task-card ${statusCls}" data-task-id="${t.task_id}" data-type="${t.task_type}" data-chapter="${t.chapter}" ${sectionAttr} ${chapterLevelAttr} style="cursor:pointer">
                <div class="task-icon">${icon}</div>
                <div class="task-info">
                    <div class="task-title">${t.title}</div>
                    <div class="task-meta">${t.chapter} • ${t.task_type.toUpperCase()}${t.section_id ? " • §" + t.section_id : isChapterLevel ? " • FINAL" : ""}</div>
                </div>
                <div class="task-status-badge ${statusCls}">${statusLabel}</div>
            </div>
        `;
  }).join("");

  bindTaskCardClicks(container);
}

function bindTaskCardClicks(container) {
  // Bind task clicks — route section tasks to section functions
  container.querySelectorAll(".task-card").forEach(card => {
    card.addEventListener("click", () => {
      const type = card.dataset.type;
      const chapter = card.dataset.chapter;
      const taskId = card.dataset.taskId;
      const sectionId = card.dataset.sectionId;
      const isChapterLevel = card.dataset.chapterLevel === "true";

      // Extract chapter number from "Chapter N"
      const match = chapter.match(/Chapter (\d+)/);
      const chNum = match ? parseInt(match[1]) : 1;

      if (sectionId) {
        // Section-level task
        if (type === "read") {
          openSectionReading(chNum, sectionId, false, taskId);
        } else if (type === "test") {
          openSectionTest(chNum, sectionId, false, taskId);
        }
      } else if (type === "read") {
        openReading(chNum, taskId);
      } else if (type === "test") {
        openTest(chNum, taskId);
      }
    });
  });
}

function checkWeekComplete(tasks, learnerId) {
  if (!tasks || tasks.length === 0) return;
  const allDone = tasks.every(t => t.status === "completed" || t.status.startsWith("completed"));

  if (allDone) {
    const container = $("current-tasks");
    container.innerHTML += `
            <div style="text-align:center; margin-top:16px;">
                <button class="btn btn-success" id="btn-advance-week" style="padding:14px 28px; font-size:1rem;">
                    All done! Advance to next week
                </button>
            </div>
        `;
    $("btn-advance-week").addEventListener("click", () => advanceWeek(learnerId));
  }
}

async function advanceWeek(learnerId) {
  const btn = $("btn-advance-week");
  if (btn) { btn.disabled = true; btn.textContent = "Advancing..."; }

  try {
    const result = await api(`/learning/week/advance?learner_id=${learnerId}`, { method: "POST" });
    alert(result.message);
    loadDashboard();
  } catch (err) {
    alert("Error: " + err.message);
    if (btn) { btn.disabled = false; btn.textContent = "Advance to next week"; }
  }
}

function renderChapters(chapters) {
  $("chapters-grid").innerHTML = chapters.map(ch => `
        <div class="chapter-card ${ch.status}" data-chapter-number="${ch.chapter_number}" style="cursor:pointer" title="Click to see subsection details">
            <div class="chapter-name">Ch ${ch.chapter_number}: ${ch.title}</div>
            <div class="chapter-status-text">${ch.status.replace(/_/g, " ")}</div>
        </div>
    `).join("");

  // Bind chapter card clicks for drill-down
  $("chapters-grid").querySelectorAll(".chapter-card").forEach(card => {
    card.addEventListener("click", () => {
      const chNum = parseInt(card.dataset.chapterNumber);
      openChapterDetail(chNum);
    });
  });
}

let confidenceChart = null;
function renderConfidence(confData) {
  // Render Chart.js bar chart
  try {
    const ctx = $("confidence-chart");
    if (ctx && typeof Chart !== "undefined") {
      if (confidenceChart) confidenceChart.destroy();
      const labels = confData.map(c => `Ch ${c.chapter_number}`);
      const scores = confData.map(c => (c.mastery_score * 100));
      const colors = confData.map(c =>
        c.mastery_band === "mastered" ? "#22c55e" :
          c.mastery_band === "proficient" ? "#3b82f6" :
            c.mastery_band === "developing" ? "#f59e0b" : "#ef4444"
      );
      confidenceChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [{
            label: "Mastery %",
            data: scores,
            backgroundColor: colors.map(c => c + "cc"),
            borderColor: colors,
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: false },
            title: { display: true, text: "Chapter Mastery Overview", color: "#94a3b8", font: { size: 14 } }
          },
          scales: {
            y: { beginAtZero: true, max: 100, ticks: { color: "#64748b" }, grid: { color: "#1e293b55" } },
            x: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { display: false } },
          },
        },
      });
    }
  } catch (e) { console.warn("Chart rendering skipped:", e); }

  // Render confidence cards grid
  $("confidence-grid").innerHTML = confData.map(ch => {
    const pct = (ch.mastery_score * 100).toFixed(0);
    const barColor = ch.mastery_band === "mastered" ? "var(--success)" :
      ch.mastery_band === "proficient" ? "var(--info)" :
        ch.mastery_band === "developing" ? "var(--warning)" : "var(--danger)";
    return `
            <div class="confidence-card">
                <div class="confidence-header">
                    <span class="confidence-chapter">Ch ${ch.chapter_number}</span>
                    <span class="mastery-badge ${ch.mastery_band}">${ch.mastery_band}</span>
                </div>
                <div class="confidence-bar">
                    <div class="confidence-bar-fill" style="width:${pct}%; background:${barColor}"></div>
                </div>
                <div class="confidence-score">Score: ${pct}% • Attempts: ${ch.attempt_count}${ch.revision_queued ? " • ? Revision" : ""}</div>
            </div>
        `;
  }).join("");
}

function renderPlan(plan, currentWeek) {
  if (!plan || plan.length === 0) {
    $("plan-timeline").innerHTML = `<p style="color:var(--text-muted)">No plan generated yet.</p>`;
    return;
  }

  $("plan-timeline").innerHTML = plan.map(p => {
    const statusCls = p.status || (p.week < currentWeek ? "completed" : p.week === currentWeek ? "current" : "upcoming");
    return `
            <div class="plan-week ${statusCls}">
                <div class="plan-week-num">W${p.week}</div>
                <div class="plan-week-info">
                    <div class="plan-week-chapter">${p.week_label || p.chapter}</div>
                    <div class="plan-week-focus">${p.focus || ""}</div>
                </div>
            </div>
        `;
  }).join("");
}

function renderRevision(revisions) {
  $("revision-list").innerHTML = revisions.map(r => `
        <div class="revision-item">
            <div class="revision-icon">Plan</div>
            <div class="revision-info">
                <div class="revision-chapter">${r.chapter}</div>
                <div class="revision-reason">${r.reason}</div>
            </div>
        </div>
    `).join("");
}


// -- READING -----------------------------------------------------------------
async function openReading(chapterNumber, taskId) {
  showScreen("reading");
  if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
  readingTaskId = taskId;
  if (!readingTaskId) {
    const resolvedTaskMeta = await resolveCurrentWeekTask("read", chapterNumber, null);
    readingTaskId = resolvedTaskMeta?.task_id || null;
  }
  readingChapterNumber = chapterNumber;
  readingSeconds = 0;
  let requiredReadingSeconds = 60;
  let readingTaskCompleted = false;
  let completionInFlight = false;
  let contentLoaded = false;

  const attemptMarkReadingComplete = async () => {
    if (readingTaskCompleted || completionInFlight) return;
    completionInFlight = true;
    const completion = await completeReading();
    completionInFlight = false;
    if (completion.ok) {
      readingTaskCompleted = true;
      if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
      $("reading-status").className = "reading-status complete";
      $("reading-status").textContent = "? Reading complete! You can go back to dashboard.";
      return;
    }
    const hintedSeconds = parseMinSecondsFromReason(completion.reason);
    if (hintedSeconds) requiredReadingSeconds = Math.max(requiredReadingSeconds, hintedSeconds);
    const requiredMinutes = Math.max(1, Math.ceil(requiredReadingSeconds / 60));
    $("reading-status").className = "reading-status in-progress";
    $("reading-status").textContent = `Keep reading... (min ${requiredMinutes} minute${requiredMinutes > 1 ? "s" : ""})`;
  };

  $("reading-chapter-title").textContent = "Loading...";
  $("reading-content").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Generating reading material from NCERT...</p></div>`;
  $("reading-status").className = "reading-status in-progress";
  $("reading-status").textContent = "Calculating required read time...";

  // Start timer
  $("reading-timer").textContent = "Time: 0:00";
  readingTimer = setInterval(async () => {
    readingSeconds++;
    $("reading-timer").textContent = `Time: ${formatTime(readingSeconds)}`;

    if (contentLoaded && !readingTaskCompleted && readingSeconds >= requiredReadingSeconds) {
      await attemptMarkReadingComplete();
    }
  }, 1000);

  try {
    const content = await api("/learning/content", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        chapter_number: chapterNumber,
        regenerate: false,
        task_id: readingTaskId || null,
      },
    });
    const parsedRequired = parseInt(content.required_read_seconds, 10);
    const contentRequired = Number.isFinite(parsedRequired) && parsedRequired > 0 ? parsedRequired : 60;
    requiredReadingSeconds = contentRequired;
    contentLoaded = true;
    if (readingTaskId && !readingTaskCompleted && readingSeconds >= requiredReadingSeconds) {
      await attemptMarkReadingComplete();
    }
    const requiredMinutes = Math.max(1, Math.ceil(requiredReadingSeconds / 60));
    if (!readingTaskCompleted) {
      $("reading-status").className = "reading-status in-progress";
      $("reading-status").textContent = `Keep reading... (min ${requiredMinutes} minute${requiredMinutes > 1 ? "s" : ""})`;
    }

    const sourceBadge = content.source === "cached"
      ? `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">CACHED</span>`
      : `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">FRESH</span>`;
    $("reading-chapter-title").innerHTML = `Chapter: ${content.chapter_title} ${sourceBadge}`;
    $("reading-content").innerHTML = `
      <div class="source-link-row">
        <button class="btn btn-sm btn-outline" onclick="openChapterSource(${chapterNumber}, '${String(content.chapter_title || "").replace(/'/g, "\\'")}')">View chapter source overview</button>
      </div>
      ${mdToHtml(content.content)}
    `;
    renderKaTeX($("reading-content"));
    if (readingTaskCompleted) {
      $("reading-status").className = "reading-status complete";
      $("reading-status").innerHTML = `
        ? Reading complete
        <button onclick="openReading(${chapterNumber}, ${readingTaskId ? `'${readingTaskId}'` : "null"})" style="margin-left:12px;padding:4px 12px;font-size:0.8rem;background:var(--warning);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">Reload</button>
        <button onclick="regenerateChapterReading(${chapterNumber}, ${readingTaskId ? `'${readingTaskId}'` : "null"})" style="margin-left:8px;padding:4px 12px;font-size:0.8rem;background:var(--info);color:white;border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">? Regenerate</button>
      `;
    }
  } catch (err) {
    $("reading-content").innerHTML = `<p style="color:var(--danger)">Error loading content: ${err.message}</p>`;
  }
}

async function completeReading() {
  if (!readingTaskId) return { ok: true, reason: "No task tracking required." };
  try {
    const result = await api("/learning/reading/complete", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        task_id: readingTaskId,
        time_spent_seconds: readingSeconds,
      },
    });
    return { ok: !!result.accepted, reason: result.reason || "" };
  } catch (err) {
    console.warn("Reading completion failed:", err);
    return { ok: false, reason: err.message || "completion request failed" };
  }
}

function backToDashboard() {
  if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
  if (testTimer) { clearInterval(testTimer); testTimer = null; }
  showScreen("dashboard");
  loadDashboard();
}


// -- CHAPTER TEST ------------------------------------------------------------
async function openTest(chapterNumber, taskId = null, regenerate = false) {
  showScreen("test");
  testSeconds = 1200;

  $("test-chapter-title").textContent = regenerate ? "Regenerating test..." : "Loading test...";
  $("chapter-test-questions").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>${regenerate ? "Generating new test questions..." : "Generating test questions..."}</p></div>`;
  $("btn-submit-chapter-test").disabled = true;
  hide($("test-result-feedback"));

  try {
    const testResp = await api("/learning/test/generate", {
      method: "POST",
      body: { learner_id: getLearnerId(), chapter_number: chapterNumber, regenerate },
    });

    if (testResp.blocked) {
      showScreen("dashboard");
      loadDashboard();
      showFinalTestBlockedModal(chapterNumber, testResp.reason_code, testResp.pending_tasks || []);
      return;
    }

    currentTestData = {
      test_id: testResp.test_id,
      questions: testResp.questions,
      chapter: testResp.chapter,
      chapter_number: chapterNumber,
      task_id: taskId,
      regenerate,
    };

    let sourceBadge = "";
    if (regenerate) {
      sourceBadge = `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">REGENERATED</span>`;
    } else if (testResp.source === "cached") {
      sourceBadge = `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">CACHED</span>`;
    } else {
      sourceBadge = `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">FRESH</span>`;
    }
    $("test-chapter-title").innerHTML = `Test: ${testResp.chapter} ${sourceBadge}`;
    renderChapterTestQuestions(testResp.questions);
    startChapterTestTimer();
  } catch (err) {
    $("chapter-test-questions").innerHTML = `<p style="color:var(--danger)">Error generating test: ${err.message}</p>`;
  }
}

function renderChapterTestQuestions(questions) {
  const container = $("chapter-test-questions");
  container.innerHTML = "";

  questions.forEach((q, i) => {
    const card = document.createElement("div");
    card.className = "question-card";
    card.id = `chtest-q-${q.question_id}`;

    card.innerHTML = `
            <div class="question-number">Question ${i + 1} of ${questions.length}</div>
            <div class="question-prompt">${mdInlineToHtml(q.prompt || "")}</div>
            <div class="question-options">
                ${q.options.map((opt, oi) => `
                    <label class="option-label" data-qid="${q.question_id}" data-idx="${oi}">
                        <input type="radio" name="chtest_${q.question_id}" value="${oi}">
                        <span class="option-indicator"></span>
                        <span>${mdInlineToHtml(opt || "")}</span>
                    </label>
                `).join("")}
            </div>
        `;
    container.appendChild(card);
  });

  container.querySelectorAll(".option-label").forEach(label => {
    label.addEventListener("click", () => {
      const qid = label.dataset.qid;
      container.querySelectorAll(`[data-qid="${qid}"]`).forEach(l => l.classList.remove("selected"));
      label.classList.add("selected");
      label.querySelector("input").checked = true;
      $(`chtest-q-${qid}`).classList.add("answered");

      const answered = container.querySelectorAll(".question-card.answered").length;
      $("btn-submit-chapter-test").disabled = answered === 0;
    });
  });

  renderKaTeX(container);
}

function startChapterTestTimer() {
  const timerEl = $("chapter-test-timer");
  timerEl.textContent = formatTime(testSeconds);
  timerEl.classList.remove("danger");

  testTimer = setInterval(() => {
    testSeconds--;
    timerEl.textContent = formatTime(testSeconds);
    if (testSeconds <= 120) timerEl.classList.add("danger");
    if (testSeconds <= 0) {
      clearInterval(testTimer);
      handleSubmitChapterTest();
    }
  }, 1000);
}

async function handleSubmitChapterTest() {
  if (testTimer) { clearInterval(testTimer); testTimer = null; }
  $("btn-submit-chapter-test").disabled = true;
  $("btn-submit-chapter-test").textContent = "Submitting...";

  const answers = [];
  currentTestData.questions.forEach(q => {
    const selected = document.querySelector(`input[name="chtest_${q.question_id}"]:checked`);
    answers.push({
      question_id: q.question_id,
      selected_index: selected ? parseInt(selected.value) : -1,
    });
  });

  try {
    const result = await api("/learning/test/submit", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        test_id: currentTestData.test_id,
        answers: answers.filter(a => a.selected_index >= 0),
        task_id: currentTestData.task_id || null,
      },
    });

    // Show feedback
    const feedbackEl = $("test-result-feedback");
    show(feedbackEl);

    let cls = "passed";
    if (result.decision === "retry") cls = "retry";
    else if (result.decision === "move_on_revision") cls = "failed";

    feedbackEl.className = `test-feedback ${cls}`;
    const retakeAction = currentTestData.section_id
      ? `openSectionTest(${currentTestData.chapter_number}, '${currentTestData.section_id}', false, ${currentTestData.task_id ? `'${currentTestData.task_id}'` : "null"})`
      : `openTest(${currentTestData.chapter_number}, ${currentTestData.task_id ? `'${currentTestData.task_id}'` : "null"}, false)`;
    const regenerateAction = currentTestData.section_id
      ? `openSectionTest(${currentTestData.chapter_number}, '${currentTestData.section_id}', true, ${currentTestData.task_id ? `'${currentTestData.task_id}'` : "null"})`
      : `openTest(${currentTestData.chapter_number}, ${currentTestData.task_id ? `'${currentTestData.task_id}'` : "null"}, true)`;
    const questionReviewHtml = (result.question_results || []).map((q, idx) => {
      const state = q.is_correct ? "correct" : "wrong";
      const selectedText = (typeof q.selected_index === "number" && q.selected_index >= 0 && q.options && q.options[q.selected_index] !== undefined)
        ? q.options[q.selected_index]
        : "Not answered";
      const correctText = (typeof q.correct_index === "number" && q.options && q.options[q.correct_index] !== undefined)
        ? q.options[q.correct_index]
        : "N/A";
      const explainBtn = q.is_correct
        ? `<button class="btn btn-outline" style="padding:6px 10px;font-size:0.8rem" onclick="explainQuestion('${q.question_id}', ${q.selected_index ?? -1}, false)">Explain</button>`
        : `<button class="btn btn-primary" style="padding:6px 10px;font-size:0.8rem" onclick="explainQuestion('${q.question_id}', ${q.selected_index ?? -1}, false)">Explain</button>`;
      return `
        <div style="text-align:left;border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-top:8px;background:var(--bg-elevated)">
          <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
            <strong>Q${idx + 1}. ${mdInlineToHtml(q.prompt || q.question_id)}</strong>
            <span class="task-status-badge ${state === "correct" ? "completed" : "pending"}">${state === "correct" ? "Correct" : "Wrong"}</span>
          </div>
          <div style="margin-top:6px;color:var(--text-secondary);font-size:0.9rem">Your answer: <strong>${mdInlineToHtml(selectedText)}</strong></div>
          <div style="color:var(--text-secondary);font-size:0.9rem">Correct answer: <strong>${mdInlineToHtml(correctText)}</strong></div>
          <div style="margin-top:8px">${explainBtn}</div>
          <div id="explain-${q.question_id}" style="margin-top:8px;color:var(--text-secondary);font-size:0.9rem"></div>
        </div>
      `;
    }).join("");

    feedbackEl.innerHTML = `
            <h3>${result.score >= 0.6 ? "Passed" : "Needs Work"} Score: ${result.correct}/${result.total} (${(result.score * 100).toFixed(0)}%)</h3>
            <p>${result.message}</p>
            <div style="margin-top:14px; display:flex; gap:10px; justify-content:center;">
                <button class="btn btn-primary" onclick="${retakeAction}">Retake Test</button>
                <button class="btn btn-outline" onclick="${regenerateAction}">? Regenerate</button>
                <button class="btn btn-secondary" onclick="backToDashboard()">Dashboard</button>
            </div>
            <div style="margin-top:14px;text-align:left">
              <h4 style="margin-bottom:8px">Question Review</h4>
              ${questionReviewHtml || `<p style="color:var(--text-muted)">Question-wise review is unavailable for this attempt.</p>`}
            </div>
        `;
    renderKaTeX(feedbackEl);

    $("btn-submit-chapter-test").textContent = "Submit Test";
  } catch (err) {
    alert("Error submitting test: " + err.message);
    $("btn-submit-chapter-test").disabled = false;
    $("btn-submit-chapter-test").textContent = "Submit Test";
  }
}


// -- CHAPTER DETAIL DRILL-DOWN -----------------------------------------------
async function openChapterDetail(chapterNumber) {
  const learnerId = getLearnerId();
  if (!learnerId) return;

  try {
    const data = await api(`/learning/chapter/${chapterNumber}/sections/${learnerId}`);
    const sections = data.sections || [];

    // Build modal overlay
    let existingOverlay = document.getElementById("chapter-detail-overlay");
    if (existingOverlay) existingOverlay.remove();

    const overlay = document.createElement("div");
    overlay.id = "chapter-detail-overlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);z-index:1000;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);";

    const bandColor = (band) => band === "mastered" ? "var(--success)" : band === "proficient" ? "var(--info)" : band === "developing" ? "var(--warning)" : "var(--danger)";

    const sectionsHtml = sections.map(s => {
      const pct = (s.best_score * 100).toFixed(0);
      const readIcon = s.reading_completed ? "?" : "?";
      return `
        <div style="background:var(--bg-elevated);border-radius:var(--radius-sm);padding:14px 16px;margin-bottom:10px;border-left:4px solid ${bandColor(s.mastery_band)};border:1px solid var(--border);border-left:4px solid ${bandColor(s.mastery_band)}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <strong style="color:var(--text-primary);font-size:0.95rem">${s.section_id} ${s.section_title}</strong>
            <span class="mastery-badge ${s.mastery_band}">${s.mastery_band}</span>
          </div>
          <div style="display:flex;gap:10px;align-items:center;font-size:0.83rem;color:var(--text-secondary);margin-bottom:8px">
            <span>${readIcon} ${s.reading_completed ? "Read" : "Not read"}</span>
            <span style="color:var(--text-muted)">•</span>
            <span>Score: <strong style="color:var(--accent-light)">${pct}%</strong></span>
            <span style="color:var(--text-muted)">•</span>
            <span>Attempts: ${s.attempt_count}</span>
          </div>
        </div>
      `;
    }).join("");

    overlay.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);max-width:620px;width:92%;max-height:82vh;overflow-y:auto;padding:28px;position:relative;box-shadow:var(--shadow);">
        <button onclick="document.getElementById('chapter-detail-overlay').remove()" style="position:absolute;top:14px;right:18px;background:var(--bg-elevated);border:1px solid var(--border);width:32px;height:32px;border-radius:50%;font-size:1.1rem;cursor:pointer;color:var(--text-secondary);display:flex;align-items:center;justify-content:center;font-family:var(--font)">&times;</button>
        <h3 style="margin-bottom:6px;color:var(--text-primary);font-size:1.25rem">Chapter ${chapterNumber}: ${data.chapter_title}</h3>
        <p style="color:var(--text-muted);margin-bottom:20px;font-size:0.85rem">${sections.length} subsections • Progress status overview</p>
        ${sectionsHtml}
      </div>
    `;

    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  } catch (err) {
    alert("Error loading chapter details: " + err.message);
  }
}

async function openSectionReading(chapterNumber, sectionId, regenerate = false, taskId = null) {
  // Close detail overlay
  const overlay = document.getElementById("chapter-detail-overlay");
  if (overlay) overlay.remove();

  showScreen("reading");
  if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
  readingChapterNumber = chapterNumber;
  readingSeconds = 0;
  readingTaskId = taskId;
  if (!readingTaskId) {
    const resolvedTaskMeta = await resolveCurrentWeekTask("read", chapterNumber, sectionId);
    readingTaskId = resolvedTaskMeta?.task_id || null;
  }

  $("reading-chapter-title").textContent = regenerate ? "Regenerating section content..." : "Loading section content...";
  $("reading-content").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>${regenerate ? "Regenerating fresh content from NCERT..." : "Loading section reading material..."}</p></div>`;
  $("reading-status").className = "reading-status in-progress";
  $("reading-status").textContent = readingTaskId
    ? "Calculating required read time..."
    : "Reading section content...";

  $("reading-timer").textContent = "Time: 0:00";
  let requiredReadingSeconds = 60;
  let sectionTaskCompleted = false;
  let completionInFlight = false;
  let contentLoaded = false;

  const attemptMarkSectionReadingComplete = async () => {
    if (sectionTaskCompleted || completionInFlight) return;
    completionInFlight = true;
    const completion = await completeReading();
    completionInFlight = false;
    if (completion.ok) {
      sectionTaskCompleted = true;
      if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
      $("reading-status").className = "reading-status complete";
      $("reading-status").innerHTML = `
        Reading complete
        <button onclick="openSectionReading(${chapterNumber}, '${sectionId}', true, ${readingTaskId ? `'${readingTaskId}'` : "null"})" style="margin-left:12px;padding:4px 12px;font-size:0.8rem;background:var(--warning);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">Regenerate</button>
        <button onclick="showScreen('dashboard');loadDashboard()" style="margin-left:8px;padding:4px 12px;font-size:0.8rem;background:var(--bg-elevated);color:var(--text-secondary);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer">Dashboard</button>
      `;
      return;
    }
    const hintedSeconds = parseMinSecondsFromReason(completion.reason);
    if (hintedSeconds) requiredReadingSeconds = Math.max(requiredReadingSeconds, hintedSeconds);
    const requiredMinutes = Math.max(1, Math.ceil(requiredReadingSeconds / 60));
    $("reading-status").className = "reading-status in-progress";
    $("reading-status").textContent = `Keep reading... (min ${requiredMinutes} minute${requiredMinutes > 1 ? "s" : ""})`;
  };

  readingTimer = setInterval(async () => {
    readingSeconds++;
    $("reading-timer").textContent = `Time: ${formatTime(readingSeconds)}`;
    if (contentLoaded && readingTaskId && !sectionTaskCompleted && readingSeconds >= requiredReadingSeconds) {
      await attemptMarkSectionReadingComplete();
    }
  }, 1000);

  try {
    const content = await api("/learning/content/section", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        chapter_number: chapterNumber,
        section_id: sectionId,
        regenerate,
        task_id: readingTaskId || null,
      },
    });
    const parsedRequired = parseInt(content.required_read_seconds, 10);
    const contentRequired = Number.isFinite(parsedRequired) && parsedRequired > 0 ? parsedRequired : 60;
    requiredReadingSeconds = contentRequired;
    contentLoaded = true;
    if (readingTaskId && !sectionTaskCompleted && readingSeconds >= requiredReadingSeconds) {
      await attemptMarkSectionReadingComplete();
    }
    const requiredMinutes = Math.max(1, Math.ceil(requiredReadingSeconds / 60));
    if (readingTaskId && !sectionTaskCompleted) {
      $("reading-status").className = "reading-status in-progress";
      $("reading-status").textContent = `Keep reading... (min ${requiredMinutes} minute${requiredMinutes > 1 ? "s" : ""})`;
    }

    const sourceBadge = content.source === "cached"
      ? `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">CACHED</span>`
      : `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">FRESH</span>`;

    $("reading-chapter-title").innerHTML = `Section ${content.section_id} - ${content.section_title} ${sourceBadge}`;
    $("reading-content").innerHTML = `
      <div class="source-link-row">
        <button class="btn btn-sm btn-outline" onclick="openSourceSection(${chapterNumber}, '${sectionId}', '${String(content.section_title || "").replace(/'/g, "\\'")}')">View original NCERT section</button>
      </div>
      ${mdToHtml(content.content)}
    `;
    renderKaTeX($("reading-content"));

    if (!readingTaskId) {
      if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
      $("reading-status").className = "reading-status complete";
      $("reading-status").innerHTML = `
        Reading complete
        <button onclick="openSectionReading(${chapterNumber}, '${sectionId}', true, ${readingTaskId ? `'${readingTaskId}'` : "null"})" style="margin-left:12px;padding:4px 12px;font-size:0.8rem;background:var(--warning);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">Regenerate</button>
        <button onclick="showScreen('dashboard');loadDashboard()" style="margin-left:8px;padding:4px 12px;font-size:0.8rem;background:var(--bg-elevated);color:var(--text-secondary);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer">Dashboard</button>
      `;
    }
  } catch (err) {
    $("reading-content").innerHTML = `<p style="color:var(--danger)">Error loading section content: ${err.message}</p>`;
  }
}

async function openSectionTest(chapterNumber, sectionId, regenerate = false, taskId = null) {
  // Close detail overlay
  const overlay = document.getElementById("chapter-detail-overlay");
  if (overlay) overlay.remove();

  showScreen("test");
  testSeconds = 600;

  $("test-chapter-title").textContent = regenerate ? "Regenerating section test..." : "Loading section test...";
  $("chapter-test-questions").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>${regenerate ? "Generating new test questions..." : "Loading section test..."}</p></div>`;
  $("btn-submit-chapter-test").disabled = true;
  hide($("test-result-feedback"));

  try {
    const testResp = await api("/learning/test/section/generate", {
      method: "POST",
      body: { learner_id: getLearnerId(), chapter_number: chapterNumber, section_id: sectionId, regenerate },
    });

    currentTestData = {
      test_id: testResp.test_id,
      questions: testResp.questions,
      chapter: testResp.chapter,
      chapter_number: chapterNumber,
      section_id: sectionId,
      task_id: taskId,
    };

    const sourceBadge = testResp.source === "cached"
      ? `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">CACHED</span>`
      : `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">FRESH</span>`;

    $("test-chapter-title").innerHTML = `Section Test: ${testResp.section_id} - ${testResp.section_title} ${sourceBadge}`;
    renderChapterTestQuestions(testResp.questions);
    $("chapter-test-questions").insertAdjacentHTML(
      "afterbegin",
      `<div class="source-link-row"><button class="btn btn-sm btn-outline" onclick="openSourceSection(${chapterNumber}, '${sectionId}', '${String(testResp.section_title || "").replace(/'/g, "\\'")}')">Open original NCERT section</button></div>`
    );
    startChapterTestTimer();
  } catch (err) {
    $("chapter-test-questions").innerHTML = `<p style="color:var(--danger)">Error generating section test: ${err.message}</p>`;
  }
}

async function loadAdminDashboard() {
  showScreen("admin");
  configureNavForRole("admin", localStorage.getItem(NAME_KEY) || "Admin");
  const overviewEl = $("admin-system-overview");
  const summaryEl = $("admin-student-summary");
  const listEl = $("admin-student-list");
  const detailEl = $("admin-student-detail");
  const agentsEl = $("admin-agent-overview");
  if (overviewEl) overviewEl.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading system overview...</p></div>`;
  if (listEl) listEl.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading students...</p></div>`;
  if (agentsEl) agentsEl.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading agent activity...</p></div>`;
  try {
    const [system, students, agents] = await Promise.all([
      api("/admin/system-overview"),
      api("/admin/students"),
      api("/admin/agents/overview"),
    ]);
    renderAdminSystemOverview(system);
    renderAdminStudentList(students);
    renderAdminAgentOverview(agents);
    if (summaryEl) {
      const studentRows = students.students || [];
      const riskCount = studentRows.filter(s => (s.risk_flags || []).length > 0).length;
      summaryEl.innerHTML = `
        <div class="comparative-card"><div class="comparative-label">Students</div><div class="comparative-value">${students.total || 0}</div></div>
        <div class="comparative-card"><div class="comparative-label">At Risk</div><div class="comparative-value">${riskCount}</div></div>
        <div class="comparative-card"><div class="comparative-label">Scheduler</div><div class="comparative-value">${system.service?.scheduler_enabled ? "Enabled" : "Disabled"}</div></div>
      `;
    }
    const firstLearnerId = (students.students || [])[0]?.learner_id;
    if (firstLearnerId) await loadAdminStudentDetail(firstLearnerId);
    else if (detailEl) detailEl.innerHTML = `<div class="admin-meta">No students available.</div>`;
  } catch (err) {
    if (overviewEl) overviewEl.innerHTML = `<div class="admin-meta">${err.message}</div>`;
    if (summaryEl) summaryEl.innerHTML = "";
    if (listEl) listEl.innerHTML = "";
    if (detailEl) detailEl.innerHTML = "";
    if (agentsEl) agentsEl.innerHTML = "";
  }
}

function renderAdminSystemOverview(data) {
  const el = $("admin-system-overview");
  if (!el) return;
  const traffic = data.traffic || {};
  const service = data.service || {};
  const infra = data.infrastructure || {};
  const req = traffic.request_metrics || {};
  const mcp = req.mcp || {};
  el.innerHTML = `
    <div class="comparative-card"><div class="comparative-label">Environment</div><div class="comparative-value">${service.environment || "local"}</div></div>
    <div class="comparative-card"><div class="comparative-label">Active Runs</div><div class="comparative-value">${service.active_runs ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">Scheduled Jobs</div><div class="comparative-value">${service.scheduled_jobs ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">Requests</div><div class="comparative-value">${req.requests_total ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">Failure Rate</div><div class="comparative-value">${req.failure_rate ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">MCP Calls</div><div class="comparative-value">${mcp.mcp_calls_total ?? 0}</div></div>
    <div class="comparative-card"><div class="comparative-label">Redis</div><div class="comparative-value">${infra.redis?.connected ? "Connected" : "Down"}</div></div>
    <div class="comparative-card"><div class="comparative-label">Email</div><div class="comparative-value">${infra.email?.mode || "unknown"}</div></div>
  `;
}

function renderAdminStudentList(data) {
  const el = $("admin-student-list");
  if (!el) return;
  const students = data.students || [];
  if (!students.length) {
    el.innerHTML = `<div class="admin-meta">No student records found.</div>`;
    return;
  }
  el.innerHTML = students.map(student => `
    <button class="admin-student-row" data-learner-id="${student.learner_id}" style="width:100%;text-align:left;background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:10px;cursor:pointer">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
        <div>
          <div style="font-weight:700;color:var(--text-primary)">${student.name || "Student"}</div>
          <div class="admin-meta">${student.username || "No username"} | Progress ${student.progress_percentage ?? 0}%</div>
        </div>
        <div class="task-status-badge ${student.risk_flags?.length ? "blocked" : "completed"}">${student.risk_flags?.length ? "Needs attention" : "Stable"}</div>
      </div>
    </button>
  `).join("");
  el.querySelectorAll("[data-learner-id]").forEach(btn => {
    btn.addEventListener("click", () => loadAdminStudentDetail(btn.dataset.learnerId));
  });
}

async function loadAdminStudentDetail(learnerId) {
  const el = $("admin-student-detail");
  if (!el) return;
  el.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading student detail...</p></div>`;
  try {
    const data = await api(`/admin/students/${learnerId}`);
    const learner = data.learner || {};
    const profile = data.profile || {};
    const comparative = data.comparative || {};
    const weakAreas = (comparative.individual?.weak_areas || []).slice(0, 5);
    el.innerHTML = `
      <div style="margin-bottom:16px">
        <h3 style="margin-bottom:4px">${learner.name || "Student"}</h3>
        <div class="admin-meta">${learner.username || "No username"} | Grade ${learner.grade_level || "N/A"}</div>
      </div>
      <div class="admin-grid">
        <div class="comparative-card"><div class="comparative-label">Progress</div><div class="comparative-value">${profile.progress_percentage ?? 0}%</div></div>
        <div class="comparative-card"><div class="comparative-label">Selected Weeks</div><div class="comparative-value">${profile.selected_timeline_weeks ?? "N/A"}</div></div>
        <div class="comparative-card"><div class="comparative-label">Forecast Weeks</div><div class="comparative-value">${profile.current_forecast_weeks ?? "N/A"}</div></div>
        <div class="comparative-card"><div class="comparative-label">Timeline Delta</div><div class="comparative-value">${profile.timeline_delta_weeks ?? 0}</div></div>
      </div>
      <div style="margin-top:16px">
        <div style="font-weight:700;margin-bottom:8px">Weak areas</div>
        <div class="comparative-action-list">${weakAreas.length ? weakAreas.map(area => `<span class="quick-pill">${area}</span>`).join("") : `<span class="admin-meta">No weak areas flagged.</span>`}</div>
      </div>
      <div style="margin-top:16px">
        <div style="font-weight:700;margin-bottom:8px">Recent events</div>
        ${(data.recent_events || []).slice(0, 5).map(event => `<div class="admin-meta">${event.event_type} | ${event.created_at || ""}</div>`).join("") || `<div class="admin-meta">No recent events.</div>`}
      </div>
    `;
  } catch (err) {
    el.innerHTML = `<div class="admin-meta">${err.message}</div>`;
  }
}

function renderAdminAgentOverview(data) {
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


// -- SCREEN MANAGEMENT -------------------------------------------------------------------
function showScreen(screenName) {
  document.querySelectorAll(".screen").forEach(s => s.classList.add("hidden"));
  const screen = $(`screen-${screenName}`);
  if (screen) screen.classList.remove("hidden");
}

function closeSourceOverlay() {
  const overlay = $("source-overlay");
  if (!overlay) return;
  hide(overlay);
}

async function openSourceSection(chapterNumber, sectionId, sectionTitle = "") {
  const overlay = $("source-overlay");
  const container = $("source-content");
  if (!overlay || !container) return;
  show(overlay);
  container.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading original NCERT section...</p></div>`;
  try {
    const learnerId = getLearnerId();
    const learnerQuery = learnerId ? `?learner_id=${encodeURIComponent(learnerId)}` : "";
    const data = await api(`/learning/source-section/${chapterNumber}/${encodeURIComponent(sectionId)}${learnerQuery}`);
    container.innerHTML = `
      <div class="source-link-row">
        <span class="task-status-badge completed">Original NCERT</span>
      </div>
      <h2 style="margin-bottom:6px">Section ${data.section_id} - ${data.section_title || sectionTitle || sectionId}</h2>
      <div class="admin-meta" style="margin-bottom:14px">${data.chapter_title} | ${data.chunk_count} grounded chunk(s)</div>
      <div class="reading-content" style="max-height:none">${mdToHtml(data.source_content)}</div>
      <div class="admin-meta" style="margin-top:12px">This is the original textbook-grounded source content, separate from the adaptive generated lesson.</div>
    `;
    renderKaTeX(container);
  } catch (err) {
    container.innerHTML = `<div class="admin-meta">${err.message}</div>`;
  }
}

async function openChapterSource(chapterNumber, chapterTitle = "") {
  const overlay = $("source-overlay");
  const container = $("source-content");
  if (!overlay || !container) return;
  show(overlay);
  container.innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Loading chapter source overview...</p></div>`;
  try {
    const learnerId = getLearnerId();
    const learnerQuery = learnerId ? `?learner_id=${encodeURIComponent(learnerId)}` : "";
    const data = await api(`/learning/source-chapter/${chapterNumber}${learnerQuery}`);
    container.innerHTML = `
      <div class="source-link-row">
        <span class="task-status-badge completed">Original NCERT</span>
      </div>
      <h2 style="margin-bottom:6px">Chapter ${data.chapter_number} - ${data.chapter_title || chapterTitle || `Chapter ${chapterNumber}`}</h2>
      <div class="admin-meta" style="margin-bottom:14px">${data.chunk_count} grounded chunk(s)</div>
      <div class="reading-content" style="max-height:none">${mdToHtml(data.source_content)}</div>
      <div class="admin-meta" style="margin-top:12px">This is the original chapter-level textbook-grounded source overview, separate from the adaptive generated lesson.</div>
    `;
    renderKaTeX(container);
  } catch (err) {
    container.innerHTML = `<div class="admin-meta">${err.message}</div>`;
  }
}


// -- DAILY PLAN ------------------------------------------------------------------------
function renderDailyPlan(tasks) {
  const container = $("daily-plan-content");
  if (!container) return;

  const withSchedule = (tasks || []).filter(t => t.scheduled_day && (t.status === "pending" || t.status === "in_progress"));
  if (withSchedule.length > 0) {
    const grouped = {};
    withSchedule.forEach(t => {
      const d = new Date(t.scheduled_day);
      const day = isNaN(d.getTime()) ? "Planned" : d.toLocaleDateString(undefined, { weekday: "short" });
      if (!grouped[day]) grouped[day] = [];
      grouped[day].push(t);
    });
    container.innerHTML = Object.entries(grouped).map(([day, dayTasks]) => `
      <div style="margin-bottom:14px">
        <div style="font-weight:700;color:var(--text-primary);margin-bottom:8px">${day}</div>
        ${dayTasks.map(t => {
        const icon = t.task_type === "read" ? "Read" : (t.chapter_level ? "Final" : "Quiz");
        const sectionAttr = t.section_id ? `data-section-id="${t.section_id}"` : "";
        return `
          <div class="task-card pending" data-task-id="${t.task_id}" data-type="${t.task_type}" data-chapter="${t.chapter}" ${sectionAttr} style="cursor:pointer;border-left:3px solid var(--accent);margin-bottom:8px">
            <div class="task-icon">${icon}</div>
            <div class="task-info">
              <div class="task-title" style="font-size:0.85rem">${t.title}</div>
              <div class="task-meta">${t.chapter}${t.section_id ? " • §" + t.section_id : ""}</div>
            </div>
          </div>`;
      }).join("")}
      </div>
    `).join("");
    bindDailyPlanTaskClicks(container);
    return;
  }

  const pending = (tasks || []).filter(t => t.status === "pending" || t.status === "in_progress");
  const todayTasks = pending.slice(0, 4);

  if (todayTasks.length === 0) {
    container.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-muted)">All caught up! No pending tasks for today.</div>`;
    return;
  }

  container.innerHTML = todayTasks.map((t, i) => {
    const icon = t.task_type === "read" ? "Read" : (t.chapter_level ? "Final" : "Quiz");
    const sectionAttr = t.section_id ? `data-section-id="${t.section_id}"` : "";
    return `
      <div class="task-card pending" data-task-id="${t.task_id}" data-type="${t.task_type}" data-chapter="${t.chapter}" ${sectionAttr} style="cursor:pointer;border-left:3px solid var(--accent)">
        <div class="task-icon">${icon}</div>
        <div class="task-info">
          <div class="task-title" style="font-size:0.85rem">${i + 1}. ${t.title}</div>
          <div class="task-meta">${t.chapter}${t.section_id ? " • §" + t.section_id : ""}</div>
        </div>
      </div>
    `;
  }).join("");

  bindDailyPlanTaskClicks(container);
}

async function regenerateChapterReading(chapterNumber, taskId) {
  showScreen("reading");
  if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
  readingTaskId = taskId;
  readingChapterNumber = chapterNumber;
  readingSeconds = 0;
  $("reading-timer").textContent = "Time: 0:00";
  $("reading-chapter-title").textContent = "Regenerating content...";
  $("reading-content").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Regenerating fresh chapter content...</p></div>`;
  try {
    const content = await api("/learning/content", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        chapter_number: chapterNumber,
        regenerate: true,
        task_id: taskId || null,
      },
    });
    $("reading-chapter-title").innerHTML = `Chapter: ${content.chapter_title} <span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">REGENERATED</span>`;
    $("reading-content").innerHTML = mdToHtml(content.content);
    renderKaTeX($("reading-content"));
  } catch (err) {
    $("reading-content").innerHTML = `<p style="color:var(--danger)">Error regenerating content: ${err.message}</p>`;
  }
}

async function explainQuestion(questionId, selectedIndex = -1, regenerate = false) {
  if (!currentTestData || !currentTestData.test_id) return;
  const target = document.getElementById(`explain-${questionId}`);
  if (!target) return;
  target.innerHTML = `<span style="color:var(--text-muted)">Loading explanation...</span>`;
  try {
    const resp = await api("/learning/test/question/explain", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        test_id: currentTestData.test_id,
        question_id: questionId,
        selected_index: selectedIndex >= 0 ? selectedIndex : null,
        regenerate: !!regenerate,
      },
    });
    const source = resp.source === "cached" ? "cached" : "generated";
    target.innerHTML = `
      <div style="border-left:3px solid var(--info);padding-left:10px">
        <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:6px">${source}</div>
        ${mdToHtml(resp.explanation || "")}
      </div>
      <div style="margin-top:6px">
        <button class="btn btn-outline" style="padding:4px 10px;font-size:0.75rem" onclick="explainQuestion('${questionId}', ${selectedIndex}, true)">Regenerate explanation</button>
      </div>
    `;
    renderKaTeX(target);
  } catch (err) {
    target.innerHTML = `<span style="color:var(--danger)">Error: ${err.message}</span>`;
  }
}

async function renderPlanHistory(learnerId) {
  const el = $("plan-history-list");
  if (!el) return;
  try {
    const data = await api(`/learning/plan-history/${learnerId}`);
    const versions = (data.versions || []).slice(0, 6);
    if (!versions.length) {
      el.innerHTML = `<div style="color:var(--text-muted)">No plan history yet.</div>`;
      return;
    }
    el.innerHTML = versions.map(v => `
      <div class="revision-item">
        <div class="revision-icon">Plan</div>
        <div class="revision-info">
          <div class="revision-chapter">Version ${v.version_number} • Week ${v.current_week}</div>
          <div class="revision-reason">${v.reason || "plan_update"} • ${(v.created_at || "").replace("T", " ").slice(0, 19)}</div>
        </div>
      </div>
    `).join("");
  } catch (err) {
    el.innerHTML = `<div style="color:var(--text-muted)">Plan history unavailable.</div>`;
  }
}

function bindDailyPlanTaskClicks(container) {
  container.querySelectorAll(".task-card").forEach(card => {
    card.addEventListener("click", () => {
      const type = card.dataset.type;
      const chapter = card.dataset.chapter;
      const sectionId = card.dataset.sectionId;
      const taskId = card.dataset.taskId;
      const match = chapter.match(/Chapter (\d+)/);
      const chNum = match ? parseInt(match[1]) : 1;
      if (sectionId) {
        if (type === "read") openSectionReading(chNum, sectionId, false, taskId);
        else if (type === "test") openSectionTest(chNum, sectionId, false, taskId);
      } else if (type === "read") openReading(chNum, card.dataset.taskId);
      else if (type === "test") openTest(chNum, taskId);
    });
  });
}

async function renderConfidenceTrend(learnerId) {
  const el = $("confidence-trend");
  if (!el) return;
  try {
    const trend = await api(`/learning/confidence-trend/${learnerId}`);
    const arrow = trend.trend === "up" ? "?" : (trend.trend === "down" ? "?" : "?");
    const latest = ((trend.latest_score || 0) * 100).toFixed(0);
    const n = (trend.points || []).length;
    el.textContent = `${arrow} Confidence trend: ${trend.trend} • Latest ${latest}% • ${n} attempts tracked`;
  } catch (err) {
    el.textContent = "Confidence trend unavailable";
  }
}


// -- PRACTICE QUESTIONS ----------------------------------------------------------------
let practiceData = null;

async function openPractice(chapterNumber, sectionId) {
  showScreen("practice");
  $("practice-title").textContent = `Practice: Section ${sectionId}`;
  $("practice-questions").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Generating practice questions...</p></div>`;
  $("btn-check-practice").disabled = true;
  hide($("practice-feedback"));

  try {
    const resp = await api("/learning/test/section/generate", {
      method: "POST",
      body: { learner_id: getLearnerId(), chapter_number: chapterNumber, section_id: sectionId },
    });
    practiceData = { test_id: resp.test_id, questions: resp.questions, chapter_number: chapterNumber, section_id: sectionId };
    renderPracticeQuestions(resp.questions);
    $("btn-check-practice").disabled = false;
    $("btn-new-practice").onclick = () => openPractice(chapterNumber, sectionId);
  } catch (err) {
    $("practice-questions").innerHTML = `<p style="color:var(--danger)">Error: ${err.message}</p>`;
  }
}

function renderPracticeQuestions(questions) {
  $("practice-questions").innerHTML = questions.map((q, i) => {
    const optionsHtml = (q.options || []).map((opt, j) => `
      <label style="display:block;padding:8px 12px;margin:4px 0;background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer">
        <input type="radio" name="practice_q${i}" value="${j}" style="margin-right:8px"> ${opt}
      </label>
    `).join("");
    return `
      <div class="test-question" style="margin-bottom:16px;padding:16px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius)">
        <p style="font-weight:600;margin-bottom:8px">Q${i + 1}. ${q.prompt || q.question_text || "Question"}</p>
        ${optionsHtml}
        <div class="practice-result" style="display:none;margin-top:8px;padding:8px;border-radius:var(--radius-sm)"></div>
      </div>
    `;
  }).join("");
  renderKaTeX($("practice-questions"));
}

function checkPractice() {
  if (!practiceData) return;
  let correct = 0;
  practiceData.questions.forEach((q, i) => {
    const selected = document.querySelector(`input[name="practice_q${i}"]:checked`);
    const resultDiv = document.querySelectorAll(".practice-result")[i];
    const correctIdx = q.correct_index !== undefined ? q.correct_index : (q.correct !== undefined ? q.correct : 0);
    if (resultDiv) {
      resultDiv.style.display = "block";
      if (selected && parseInt(selected.value) === correctIdx) {
        correct++;
        resultDiv.style.background = "var(--success-light)";
        resultDiv.style.color = "var(--success)";
        resultDiv.textContent = "? Correct!";
      } else {
        resultDiv.style.background = "var(--danger-light)";
        resultDiv.style.color = "var(--danger)";
        resultDiv.textContent = `? Incorrect. Answer: ${(q.options || [])[correctIdx] || "N/A"}`;
      }
    }
  });
  const total = practiceData.questions.length;
  const pct = ((correct / total) * 100).toFixed(0);
  const fb = $("practice-feedback");
  show(fb);
  fb.innerHTML = `<div style="text-align:center;padding:16px"><h3>Score ${correct}/${total} (${pct}%)</h3><p>${correct === total ? "Perfect!" : correct >= total * 0.6 ? "Good job!" : "Keep practicing!"}</p></div>`;
  $("btn-check-practice").disabled = true;
}

// Iteration 11 override: clearer comparative UX + weak-area drilldowns.
async function loadComparativeAnalytics(learnerId) {
  const summary = $("comparative-summary");
  const metrics = $("comparative-metrics");
  const signals = $("comparative-signals");
  const actions = $("comparative-actions");
  if (summary) summary.innerHTML = `<div style="color:var(--text-muted)">Loading comparative analytics...</div>`;
  if (metrics) metrics.innerHTML = "";
  if (signals) signals.innerHTML = "";
  if (actions) actions.innerHTML = "";
  try {
    const data = await api(`/onboarding/comparative-analytics/${learnerId}`);
    renderComparativeAnalytics(data);
  } catch (err) {
    console.warn("Comparative analytics load failed:", err);
    renderComparativeAnalyticsFallback("Comparative analytics not available yet.");
  }
}

function renderComparativeAnalytics(data) {
  const summary = $("comparative-summary");
  const metrics = $("comparative-metrics");
  const signals = $("comparative-signals");
  const actions = $("comparative-actions");
  if (!summary || !metrics || !signals || !actions) return;

  const ind = data.individual || {};
  const cmp = data.comparative || {};
  const avg = cmp.average_vs_cohort || {};
  const cluster = cmp.similar_learner_cluster || {};
  const hooks = data.hooks || {};
  const ew = hooks.early_warning_signals || {};
  const anonymized = !!data.anonymized;
  const weakAreas = Array.isArray(ind.weak_areas) ? ind.weak_areas.slice(0, 6) : [];
  const smallCohort = !anonymized || Number(data.cohort_size || 0) < 5;

  summary.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap">
      <div><strong>Cohort size:</strong> ${data.cohort_size ?? 0}</div>
      <div><strong>Privacy mode:</strong> ${anonymized ? "Anonymized metrics enabled" : "Limited (cohort too small)"}</div>
      <div><strong>Adaptive hint:</strong> ${hooks.adaptive_difficulty_hint || "maintain"}</div>
    </div>
    ${smallCohort ? `<div style="margin-top:8px;color:var(--warning)">Comparative ranks are hidden for small cohorts to avoid misleading signals.</div>` : ""}
  `;
  summary.classList.toggle("warning", smallCohort);

  const percentile = cmp.percentile_ranking;
  const learnerScore = Number(ind.topic_mastery_score || 0);
  const completion = Number(ind.completion_rate_percent || 0);
  const velocity = Number(ind.learning_velocity || 0);
  const trend = Number((cmp.trend_over_time || {}).improvement_trend || ind.improvement_trend || 0);

  metrics.innerHTML = `
    <div class="comparative-card">
      <div class="comparative-label">Mastery Score</div>
      <div class="comparative-value">${(learnerScore * 100).toFixed(1)}%</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Percentile Rank <span class="help-tip" title="Your standing compared to the cohort. Higher percentile means you are performing better than more learners.">i</span></div>
      <div class="comparative-value">${smallCohort ? "Hidden" : `${Number(percentile || 0).toFixed(1)}%`}</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Vs Cohort Delta <span class="help-tip" title="Difference between your mastery score and the cohort average. Positive means above average; negative means below average.">i</span></div>
      <div class="comparative-value">${smallCohort ? "Hidden" : `${(Number(avg.delta || 0) * 100).toFixed(1)}%`}</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Completion Rate</div>
      <div class="comparative-value">${completion.toFixed(1)}%</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Learning Velocity <span class="help-tip" title="How quickly you complete mastery milestones over recent activity windows. Higher means faster progression.">i</span></div>
      <div class="comparative-value">${velocity.toFixed(2)}</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Improvement Trend</div>
      <div class="comparative-value">${trend >= 0 ? "+" : ""}${(trend * 100).toFixed(1)}%</div>
    </div>
    <div class="comparative-card">
      <div class="comparative-label">Similar Cluster</div>
      <div class="comparative-value">${cluster.cluster_size ?? "N/A"}</div>
    </div>
  `;

  const signalRows = [
    ["Low Mastery", !!ew.low_mastery],
    ["High Timeline Drift", !!ew.timeline_drift_high],
    ["Below Cohort Avg", !!ew.below_cohort_average],
    ["Repeated Weak Performance", !!ew.repeated_weak_performance],
  ];
  signals.innerHTML = signalRows.map(([label, risk]) => `
    <div class="comparative-card">
      <div class="comparative-label">${label}</div>
      <span class="signal-chip ${risk ? "risk" : "ok"}">${risk ? "Attention" : "Stable"}</span>
    </div>
  `).join("");

  const weakAreaPills = weakAreas.length
    ? weakAreas.map(area => `<button class="quick-pill" onclick="focusWeakArea('${String(area).replace(/'/g, "\\'")}')">${area}</button>`).join("")
    : `<span style="color:var(--text-muted);font-size:0.85rem">No weak areas flagged right now.</span>`;
  const recs = [];
  if (ew.low_mastery) recs.push("Revisit a weak section and take a fresh section test.");
  if (ew.timeline_drift_high) recs.push("Finish pending week tasks before attempting the final chapter test.");
  if (ew.below_cohort_average) recs.push("Focus on consistency: 30-45 minutes daily for this week.");
  if (ew.repeated_weak_performance) recs.push("Use explanation mode on wrong answers and retry similar questions.");
  if (recs.length === 0) recs.push("Maintain current pace and continue chapter-wise progression.");

  actions.innerHTML = `
    <div class="comparative-action-card">
      <div class="comparative-label">Weak Area Drilldown</div>
      <div class="comparative-action-list">${weakAreaPills}</div>
    </div>
    <div class="comparative-action-card">
      <div class="comparative-label">Recommended Next Moves</div>
      <ul style="margin:8px 0 0 18px;color:var(--text-secondary);font-size:0.86rem">
        ${recs.slice(0, 4).map(r => `<li>${r}</li>`).join("")}
      </ul>
    </div>
  `;
}

function renderComparativeAnalyticsFallback(message) {
  const summary = $("comparative-summary");
  const metrics = $("comparative-metrics");
  const signals = $("comparative-signals");
  const actions = $("comparative-actions");
  if (!summary || !metrics || !signals || !actions) return;
  summary.classList.remove("warning");
  summary.innerHTML = `<div style="color:var(--text-muted)">${message || "Comparative analytics unavailable."}</div>`;
  metrics.innerHTML = "";
  signals.innerHTML = "";
  actions.innerHTML = "";
}

function focusWeakArea(areaLabel) {
  const area = String(areaLabel || "").trim();
  if (!area) return;
  const cards = Array.from(document.querySelectorAll("#current-tasks .task-card"));
  let matched = 0;
  cards.forEach(card => {
    const chapter = String(card.dataset.chapter || "");
    const isMatch = chapter.toLowerCase().includes(area.toLowerCase());
    card.style.outline = isMatch ? "2px solid var(--warning)" : "";
    card.style.outlineOffset = isMatch ? "2px" : "";
    if (isMatch) matched += 1;
  });
  const tasksSection = $("section-tasks");
  if (tasksSection) tasksSection.scrollIntoView({ behavior: "smooth", block: "start" });
  if (matched === 0) {
    alert(`No current-week tasks found for ${area}. Try reviewing chapter cards below.`);
  }
}


