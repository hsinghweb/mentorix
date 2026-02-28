const AUTH_TOKEN_KEY = "mentorix_token";
const LEARNER_ID_KEY = "mentorix_learner_id";
const API_BASE_KEY = "mentorix_api_base";

function el(id) {
  return document.getElementById(id);
}
function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}
function getStoredLearnerId() {
  return localStorage.getItem(LEARNER_ID_KEY) || "";
}
function setAuth(token, learnerId, apiBase) {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, String(token));
  if (learnerId != null && learnerId !== "") localStorage.setItem(LEARNER_ID_KEY, String(learnerId));
  if (apiBase != null && String(apiBase).trim()) localStorage.setItem(API_BASE_KEY, String(apiBase).trim().replace(/\/+$/, ""));
}
function clearAuth() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(LEARNER_ID_KEY);
}
function getAuthBaseUrl() {
  const input = el("authApiBase");
  const fromInput = input && input.value && String(input.value).trim().replace(/\/+$/, "");
  return fromInput || localStorage.getItem(API_BASE_KEY) || "http://localhost:8000";
}
function showAuthGate() {
  if (el("auth-gate")) el("auth-gate").classList.remove("hidden");
  if (el("app-main")) el("app-main").classList.add("hidden");
}
function showApp() {
  if (el("auth-gate")) el("auth-gate").classList.add("hidden");
  if (el("app-main")) el("app-main").classList.remove("hidden");
  const lid = getStoredLearnerId();
  if (lid) loadLandingOverview().catch(() => {});
}
function showAuthPanel(name) {
  ["auth-login", "auth-signup", "auth-diagnostic", "auth-result"].forEach((id) => {
    const p = el(id);
    if (p) p.classList.toggle("hidden", id !== "auth-" + name);
  });
}

function logStatus(message, data) {
  const statusEl = el("status");
  if (!statusEl) return;
  const stamp = new Date().toLocaleTimeString();
  const suffix = data ? `\n${JSON.stringify(data, null, 2)}` : "";
  statusEl.textContent = `[${stamp}] ${message}${suffix}`;
}

function newUuid() {
  return crypto.randomUUID();
}

function getBaseUrl() {
  const base = localStorage.getItem(API_BASE_KEY) || "http://localhost:8000";
  return (typeof base === "string" ? base : "").trim().replace(/\/+$/, "") || "http://localhost:8000";
}

function getObBaseUrl() {
  return (el("obApiBase") && el("obApiBase").value.trim().replace(/\/+$/, "")) || getBaseUrl();
}

function getAdminBaseUrl() {
  return (el("adminApiBase") && el("adminApiBase").value.trim().replace(/\/+$/, "")) || getBaseUrl();
}

async function loadLandingOverview() {
  const learnerId = getStoredLearnerId();
  if (!learnerId) return;
  const base = getBaseUrl();
  const rootCompletion = el("courseCompletionRoot");
  const rootProfile = el("profileConfidenceRoot");
  const rootSchedule = el("scheduleRoot");
  function setError(where, msg) {
    if (where) where.innerHTML = "<p class=\"muted\">" + (msg || "Could not load.") + "</p>";
  }
  try {
    const [syllabusResp, standResp, scheduleResp] = await Promise.all([
      fetch(`${base}/onboarding/syllabus`).then((r) => r.ok ? r.json() : { chapters: [] }),
      fetch(`${base}/onboarding/where-i-stand/${learnerId}`).then((r) => r.json()),
      fetch(`${base}/onboarding/schedule/${learnerId}`).then((r) => r.ok ? r.json() : null),
    ]);
    const syllabus = syllabusResp.chapters || [];
    renderCourseCompletion(rootCompletion, syllabus, standResp);
    renderProfileConfidence(rootProfile, syllabus, standResp);
    renderSchedule(rootSchedule, scheduleResp);
  } catch (err) {
    setError(rootCompletion, "Could not load course completion.");
    setError(rootProfile, "Could not load profile.");
    setError(rootSchedule, "Could not load schedule.");
  }
}

function renderCourseCompletion(root, syllabus, standData) {
  if (!root) return;
  const status = (standData && standData.chapter_status) || [];
  const byChapter = {};
  status.forEach((s) => {
    const ch = s.chapter || s.name || "";
    if (ch) byChapter[ch] = s;
  });
  if (!syllabus.length) {
    root.innerHTML = "<p class=\"muted\">No syllabus data. Showing chapter list from profile.</p>";
    const rows = [];
    for (let i = 1; i <= 14; i += 1) {
      const chName = "Chapter " + i;
      const entry = byChapter[chName] || null;
      const score = entry && typeof entry.score === "number" ? entry.score : null;
      const completed = score !== null && score >= 0.7;
      rows.push("<tr><td>" + chName + "</td><td>" + (completed ? "Completed" : "Not completed yet") + "</td></tr>");
    }
    root.innerHTML = "<table class=\"status-table\"><thead><tr><th>Chapter</th><th>Status</th></tr></thead><tbody>" + rows.join("") + "</tbody></table>";
    return;
  }
  const parts = syllabus.map((ch) => {
    const chName = "Chapter " + ch.number;
    const entry = byChapter[chName] || null;
    const score = entry && typeof entry.score === "number" ? entry.score : null;
    const completed = score !== null && score >= 0.7;
    const statusLabel = completed ? "Completed" : "Not completed yet";
    const subtopicsHtml = (ch.subtopics || []).map((st) => "<li class=\"subtopic\"><span class=\"subtopic-id\">" + escapeHtml(st.id) + "</span> " + escapeHtml(st.title) + " — <span class=\"subtopic-status\">" + (completed ? "Done" : "—") + "</span></li>").join("");
    return "<div class=\"chapter-block\"><h3 class=\"chapter-title\">" + escapeHtml(chName) + " · " + escapeHtml(ch.title) + "</h3><p class=\"chapter-status\">" + statusLabel + "</p><ul class=\"subtopic-list\">" + subtopicsHtml + "</ul></div>";
  });
  root.innerHTML = parts.join("");
}

function renderProfileConfidence(root, syllabus, standData) {
  if (!root) return;
  const status = (standData && standData.chapter_status) || [];
  const byChapter = {};
  status.forEach((s) => {
    const ch = s.chapter || s.name || "";
    if (ch) byChapter[ch] = s;
  });
  const confidencePct = standData && typeof standData.confidence_score === "number" ? (standData.confidence_score * 100).toFixed(0) + "%" : "—";
  let body = "<p class=\"profile-summary\">Overall confidence: <strong>" + confidencePct + "</strong></p>";
  if (!syllabus.length) {
    const rows = [];
    for (let i = 1; i <= 14; i += 1) {
      const chName = "Chapter " + i;
      const entry = byChapter[chName] || null;
      const perc = entry && typeof entry.score === "number" ? (entry.score * 100).toFixed(0) + "%" : "—";
      const band = entry && entry.band ? entry.band : "Not started";
      rows.push("<tr><td>" + chName + "</td><td>" + perc + "</td><td>" + escapeHtml(band) + "</td></tr>");
    }
    root.innerHTML = body + "<table class=\"status-table\"><thead><tr><th>Chapter</th><th>Accuracy</th><th>Level</th></tr></thead><tbody>" + rows.join("") + "</tbody></table>";
    return;
  }
  const parts = syllabus.map((ch) => {
    const chName = "Chapter " + ch.number;
    const entry = byChapter[chName] || null;
    const perc = entry && typeof entry.score === "number" ? (entry.score * 100).toFixed(0) + "%" : "—";
    const band = entry && entry.band ? entry.band : "Not started";
    const subtopicsHtml = (ch.subtopics || []).map((st) => "<li class=\"subtopic\"><span class=\"subtopic-id\">" + escapeHtml(st.id) + "</span> " + escapeHtml(st.title) + " — <span class=\"subtopic-accuracy\">" + (entry ? perc : "—") + " / " + escapeHtml(band) + "</span></li>").join("");
    return "<div class=\"chapter-block\"><h3 class=\"chapter-title\">" + escapeHtml(chName) + " · " + escapeHtml(ch.title) + "</h3><p class=\"chapter-accuracy\">Accuracy: " + perc + " · " + escapeHtml(band) + "</p><ul class=\"subtopic-list\">" + subtopicsHtml + "</ul></div>";
  });
  root.innerHTML = body + parts.join("");
}

function renderSchedule(root, scheduleData) {
  if (!root) return;
  if (!scheduleData || !scheduleData.weeks || !scheduleData.weeks.length) {
    root.innerHTML = "<p class=\"muted\">No schedule data yet.</p>";
    return;
  }
  const currentWeek = scheduleData.current_week;
  const parts = scheduleData.weeks.map((w) => {
    const isPast = w.is_past;
    const isCurrent = w.is_current;
    let badge = "";
    if (isCurrent) badge = " <span class=\"week-badge current\">Current</span>";
    else if (isPast) badge = " <span class=\"week-badge past\">Past</span>";
    const taskRows = (w.tasks || []).map((t) => "<tr><td>" + escapeHtml(t.title || t.chapter || "Task") + "</td><td>" + escapeHtml(t.task_type || "—") + "</td><td>" + escapeHtml(t.chapter || "—") + "</td><td>" + escapeHtml(t.status || "pending") + "</td></tr>").join("");
    const taskTable = taskRows ? "<table class=\"status-table week-tasks\"><thead><tr><th>Task</th><th>Type</th><th>Chapter</th><th>Status</th></tr></thead><tbody>" + taskRows + "</tbody></table>" : "<p class=\"muted\">No tasks for this week yet.</p>";
    return "<div class=\"week-block" + (isCurrent ? " week-current" : "") + "\"><h3 class=\"week-title\">Week " + w.week_number + badge + "</h3><p class=\"week-meta\">" + escapeHtml(w.chapter || "—") + " · " + escapeHtml(w.focus || "") + "</p>" + taskTable + "</div>";
  });
  root.innerHTML = "<p class=\"muted\">Timeline: " + scheduleData.total_weeks + " weeks total. You are on week " + currentWeek + ".</p>" + parts.join("");
}

function escapeHtml(s) {
  if (s == null) return "";
  const t = document.createElement("textarea");
  t.textContent = String(s);
  return t.innerHTML;
}

function renderChapterStatusTable(data) {
  const body = el("chapStatusTableBody");
  if (!body) return;
  const status = (data && data.chapter_status) || [];
  const byChapter = {};
  status.forEach((s) => {
    const ch = s.chapter || s.name || "";
    if (ch) byChapter[ch] = s;
  });
  const rows = [];
  for (let i = 1; i <= 14; i += 1) {
    const chName = "Chapter " + i;
    const entry = byChapter[chName] || null;
    const score = entry && typeof entry.score === "number" ? entry.score : null;
    const completed = score !== null && score >= 0.7;
    const label = completed ? "Completed" : "Not completed yet";
    rows.push(`<tr><td>${chName}</td><td>${label}</td></tr>`);
  }
  body.innerHTML = rows.join("");
}

function renderChapterAccuracyTable(data) {
  const body = el("chapAccuracyTableBody");
  if (!body) return;
  const status = (data && data.chapter_status) || [];
  const byChapter = {};
  status.forEach((s) => {
    const ch = s.chapter || s.name || "";
    if (ch) byChapter[ch] = s;
  });
  const rows = [];
  for (let i = 1; i <= 14; i += 1) {
    const chName = "Chapter " + i;
    const entry = byChapter[chName] || null;
    const rawScore = entry && typeof entry.score === "number" ? entry.score : null;
    const perc = rawScore !== null ? (rawScore * 100).toFixed(0) + "%" : "—";
    const band = entry && entry.band ? entry.band : "Not started";
    rows.push(`<tr><td>${chName}</td><td>${perc}</td><td>${band}</td></tr>`);
  }
  body.innerHTML = rows.join("");
}

function renderCurrentWeekPlan(data) {
  const body = el("currentWeekTasksBody");
  const weekLabel = el("currentWeekLabel");
  if (!body) return;
  const tasks = (data && data.tasks) || [];
  const week = data && data.week_number;
  if (weekLabel) weekLabel.textContent = week != null ? String(week) : "-";
  if (!tasks.length) {
    body.innerHTML = "<tr><td colspan=\"4\">No tasks scheduled for this week yet.</td></tr>";
    return;
  }
  const rows = tasks.map((t) => {
    const title = t.title || t.chapter || "Task";
    const type = t.task_type || "task";
    const chapter = t.chapter || "—";
    const status = t.status || "pending";
    return `<tr><td>${title}</td><td>${type}</td><td>${chapter}</td><td>${status}</td></tr>`;
  });
  body.innerHTML = rows.join("");
}

async function apiCall(path, method = "GET", body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(`${getBaseUrl()}${path}`, opts);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(`${resp.status} ${resp.statusText}: ${JSON.stringify(data)}`);
  }
  return data;
}

async function apiCallOb(path, method = "GET", body = null) {
  const base = getObBaseUrl();
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(`${base}${path}`, opts);
  const data = await resp.json();
  if (!resp.ok) throw new Error(`${resp.status}: ${JSON.stringify(data)}`);
  return data;
}

async function apiCallAdmin(path) {
  const base = getAdminBaseUrl();
  const resp = await fetch(`${base}${path}`);
  const data = await resp.json();
  if (!resp.ok) throw new Error(`${resp.status}: ${JSON.stringify(data)}`);
  return data;
}

function renderStart(data) {
  el("sessionId").textContent = data.session_id ?? "-";
  el("concept").textContent = data.concept ?? "-";
  el("question").textContent = data.question ?? "-";
  el("explanation").textContent = data.explanation ?? "-";
}

function renderSubmit(data) {
  const scoreEl = el("score");
  const scoreVal = Number(data.score ?? 0);
  scoreEl.textContent = String(data.score ?? "-");
  scoreEl.classList.remove("score-good", "score-bad");
  if (!Number.isNaN(scoreVal)) {
    scoreEl.classList.add(scoreVal >= 0.6 ? "score-good" : "score-bad");
  }
  el("errorType").textContent = data.error_type ?? "-";
  el("adaptation").textContent = JSON.stringify(data.adaptation_applied ?? {}, null, 2);
  el("explanation").textContent = data.next_explanation ?? "-";
}

function renderDashboard(data) {
  el("engagement").textContent = String(data.engagement_score ?? "-");
  el("weakAreas").textContent = (data.weak_areas || []).join(", ") || "-";
  el("masteryMap").textContent = JSON.stringify(data.mastery_map || {}, null, 2);
  el("lastSessions").textContent = JSON.stringify(data.last_sessions || [], null, 2);
}

async function startSession() {
  try {
    const learnerId = el("learnerId").value.trim();
    if (!learnerId) throw new Error("Learner ID is required");
    const data = await apiCall("/start-session", "POST", { learner_id: learnerId });
    renderStart(data);
    logStatus("Session started", data);
  } catch (err) {
    logStatus("Start session failed", { error: err.message });
  }
}

async function submitAnswer() {
  try {
    const sessionId = el("sessionId").textContent.trim();
    if (!sessionId || sessionId === "-") throw new Error("Start a session first");
    const answer = el("answer").value.trim();
    const responseTime = Number(el("responseTime").value || "0");
    const data = await apiCall("/submit-answer", "POST", {
      session_id: sessionId,
      answer,
      response_time: responseTime,
    });
    renderSubmit(data);
    logStatus("Answer submitted", data);
  } catch (err) {
    logStatus("Submit answer failed", { error: err.message });
  }
}

async function refreshDashboard() {
  try {
    const learnerId = el("learnerId").value.trim();
    if (!learnerId) throw new Error("Learner ID is required");
    const data = await apiCall(`/dashboard/${learnerId}`, "GET");
    renderDashboard(data);
    logStatus("Dashboard refreshed", data);
  } catch (err) {
    logStatus("Dashboard failed", { error: err.message });
  }
}

el("newLearnerBtn").addEventListener("click", () => {
  el("learnerId").value = newUuid();
});
el("startBtn").addEventListener("click", startSession);
el("submitBtn").addEventListener("click", submitAnswer);
el("dashboardBtn").addEventListener("click", refreshDashboard);

// Auth gate: login / signup / diagnostic flow (PLANNER_FINAL_FEATURES)
// Account is created only after the user completes the 25-question diagnostic.
const DIAGNOSTIC_TIME_LIMIT_MINUTES = 30;
let _authDiagnosticAttemptId = null;
let _authDiagnosticQuestions = [];
let _authSignupDraftId = null;
let _authDiagnosticStartTime = null;
let _authTimerInterval = null;

function initAuthTabs() {
  const tabs = document.querySelectorAll("#auth-tabs .tab");
  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      const auth = btn.getAttribute("data-auth");
      if (!auth) return;
      tabs.forEach((t) => t.classList.remove("active"));
      btn.classList.add("active");
      showAuthPanel(auth);
      const loginErr = el("authLoginError");
      const signupErr = el("authSignupError");
      if (loginErr) { loginErr.classList.add("hidden"); loginErr.textContent = ""; }
      if (signupErr) { signupErr.classList.add("hidden"); signupErr.textContent = ""; }
    });
  });
}

async function doLogin() {
  const usernameInput = el("loginUsername");
  const passwordInput = el("loginPassword");
  const username = (usernameInput && usernameInput.value && String(usernameInput.value).trim()) || "";
  const password = (passwordInput && passwordInput.value) || "";
  const base = getAuthBaseUrl();
  const errEl = el("authLoginError");
  const btnEl = el("loginBtn");

  if (!username || !password) {
    if (errEl) { errEl.textContent = "Please enter your username and password."; errEl.classList.remove("hidden"); }
    return;
  }
  if (errEl) { errEl.classList.add("hidden"); errEl.textContent = ""; }
  const originalLabel = btnEl ? btnEl.textContent : "Login";
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "Signing in…"; }
  try {
    const resp = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? (data.detail[0] && data.detail[0].msg) || data.detail[0] : data.message || resp.statusText || "Login failed.";
      throw new Error(msg);
    }
    const token = data.token;
    const learnerId = data.learner_id != null ? String(data.learner_id) : "";
    if (!token || !learnerId) throw new Error("Invalid response from server. Please try again.");
    setAuth(token, learnerId, base);
    showApp();
  } catch (err) {
    if (errEl) { errEl.textContent = err.message || "Login failed. Check your username and password."; errEl.classList.remove("hidden"); }
    if (btnEl) { btnEl.disabled = false; btnEl.textContent = originalLabel; }
  }
}

function stopAuthTimer() {
  if (_authTimerInterval) {
    clearInterval(_authTimerInterval);
    _authTimerInterval = null;
  }
}

function startAuthTimer() {
  stopAuthTimer();
  _authDiagnosticStartTime = Date.now();
  const timerEl = el("authDiagnosticTimer");
  if (!timerEl) return;
  function tick() {
    const elapsedMs = Date.now() - _authDiagnosticStartTime;
    const limitMs = DIAGNOSTIC_TIME_LIMIT_MINUTES * 60 * 1000;
    const leftMs = Math.max(0, limitMs - elapsedMs);
    const leftMin = Math.floor(leftMs / 60000);
    const leftSec = Math.floor((leftMs % 60000) / 1000);
    timerEl.textContent = "Time left: " + leftMin + ":" + (leftSec < 10 ? "0" : "") + leftSec;
    if (leftMs <= 0) {
      stopAuthTimer();
      timerEl.textContent = "Time's up! Submitting...";
      submitAuthDiagnostic();
    }
  }
  tick();
  _authTimerInterval = setInterval(tick, 1000);
}

async function doSignup() {
  const username = (el("signupUsername") && el("signupUsername").value && String(el("signupUsername").value).trim()) || "";
  const password = (el("signupPassword") && el("signupPassword").value) || "";
  const name = (el("signupName") && el("signupName").value && String(el("signupName").value).trim()) || "";
  const date_of_birth = (el("signupDob") && el("signupDob").value) || "";
  const math_9_percent = parseInt((el("signupMathPercent") && el("signupMathPercent").value) || "0", 10);
  const selected_timeline_weeks = parseInt((el("signupWeeks") && el("signupWeeks").value) || "28", 10);
  const base = getAuthBaseUrl();
  const errEl = el("authSignupError");
  const btnEl = el("signupBtn");

  if (!username || !password || !name || !date_of_birth) {
    if (errEl) { errEl.textContent = "Please fill in username, password, full name, and date of birth."; errEl.classList.remove("hidden"); }
    return;
  }
  if (Number.isNaN(math_9_percent) || math_9_percent < 0 || math_9_percent > 100) {
    if (errEl) { errEl.textContent = "Class 9 Maths % must be between 0 and 100."; errEl.classList.remove("hidden"); }
    return;
  }
  if (errEl) { errEl.classList.add("hidden"); errEl.textContent = ""; }
  const originalLabel = btnEl ? btnEl.textContent : "Continue to test";
  if (btnEl) { btnEl.disabled = true; btnEl.textContent = "Loading…"; }
  try {
    const resp = await fetch(`${base}/auth/start-signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, name, date_of_birth, selected_timeline_weeks, math_9_percent }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = typeof data.detail === "string" ? data.detail : Array.isArray(data.detail) ? (data.detail[0] && data.detail[0].msg) || data.detail[0] : data.message || resp.statusText || "Signup failed.";
      throw new Error(msg);
    }
    _authSignupDraftId = data.signup_draft_id;
    _authDiagnosticAttemptId = null;
    _authDiagnosticQuestions = [];
    const qResp = await fetch(`${base}/onboarding/diagnostic-questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signup_draft_id: _authSignupDraftId }),
    });
    const qData = await qResp.json().catch(() => ({}));
    if (!qResp.ok) throw new Error(qData.detail || qData.message || "Could not load the diagnostic test. Please try again.");
    _authDiagnosticAttemptId = qData.diagnostic_attempt_id;
    _authDiagnosticQuestions = qData.questions || [];
    renderAuthDiagnosticQuestions();
    startAuthTimer();
    showAuthPanel("diagnostic");
    if (el("authDiagnosticError")) { el("authDiagnosticError").classList.add("hidden"); el("authDiagnosticError").textContent = ""; }
  } catch (err) {
    if (errEl) { errEl.textContent = err.message || "Something went wrong. Please try again."; errEl.classList.remove("hidden"); }
  }
  if (btnEl) { btnEl.disabled = false; btnEl.textContent = originalLabel; }
}

function renderAuthDiagnosticQuestions() {
  const container = el("authQuestionsContainer");
  if (!container || !_authDiagnosticQuestions.length) return;
  container.innerHTML = "";
  const questions = _authDiagnosticQuestions.slice(0, 25);
  questions.forEach((q, idx) => {
    const block = document.createElement("div");
    block.className = "q-block";

    const lab = document.createElement("p");
    lab.className = "q-prompt";
    lab.innerHTML = (idx + 1) + ". " + (q.prompt || "Question");
    block.appendChild(lab);

    const opts = (q.options || []).slice(0, 4);
    const labels = ["A", "B", "C", "D"];
    opts.forEach((opt, optIdx) => {
      const optId = "auth-q-" + idx + "-opt-" + optIdx;
      const wrapper = document.createElement("label");
      wrapper.className = "q-option";

      const input = document.createElement("input");
      input.type = "radio";
      input.name = "auth-q-" + idx;
      input.id = optId;
      input.value = opt;

      const span = document.createElement("span");
      span.className = "q-option-text";
      span.innerHTML = labels[optIdx] + ". " + opt;

      wrapper.appendChild(input);
      wrapper.appendChild(span);
      block.appendChild(wrapper);
    });

    container.appendChild(block);
  });
  if (typeof renderMathInElement === "function") {
    renderMathInElement(container, {
      delimiters: [{ left: "\\(", right: "\\)" }, { left: "\\[", right: "\\]" }],
      throwOnError: false,
    });
  }
}

async function submitAuthDiagnostic() {
  stopAuthTimer();
  const base = getAuthBaseUrl();
  const useDraft = _authSignupDraftId;
  const learnerId = getStoredLearnerId();
  if (!_authDiagnosticAttemptId || !_authDiagnosticQuestions.length) {
    if (el("authDiagnosticError")) { el("authDiagnosticError").textContent = "Complete the test first."; el("authDiagnosticError").classList.remove("hidden"); }
    return;
  }
  if (!useDraft && !learnerId) {
    if (el("authDiagnosticError")) { el("authDiagnosticError").textContent = "Session expired. Please sign up again."; el("authDiagnosticError").classList.remove("hidden"); }
    return;
  }
  const elapsedMs = _authDiagnosticStartTime ? Date.now() - _authDiagnosticStartTime : DIAGNOSTIC_TIME_LIMIT_MINUTES * 60 * 1000;
  const timeSpentMinutes = Math.min(DIAGNOSTIC_TIME_LIMIT_MINUTES, Math.max(1, Math.floor(elapsedMs / 60000)));
  const answers = _authDiagnosticQuestions.slice(0, 25).map((q, idx) => {
    const selected = document.querySelector('input[name="auth-q-' + idx + '"]:checked');
    return { question_id: q.question_id, answer: (selected && selected.value) ? selected.value.trim() : "" };
  });
  const body = {
    diagnostic_attempt_id: _authDiagnosticAttemptId,
    answers,
    time_spent_minutes: timeSpentMinutes,
  };
  if (useDraft) body.signup_draft_id = useDraft;
  else body.learner_id = learnerId;
  try {
    const resp = await fetch(`${base}/onboarding/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || resp.statusText);
    if (data.token && data.learner_id) {
      setAuth(data.token, data.learner_id, base);
      _authSignupDraftId = null;
    }
    const scoreLine = data.correct_out_of_total ? "You got " + data.correct_out_of_total + " correct." : "Score: " + (data.score != null ? (data.score * 100).toFixed(1) + "%" : "-");
    const lines = [
      scoreLine,
      "",
      "You asked for: " + (data.selected_timeline_weeks || "-") + " weeks",
      "We suggest: " + (data.recommended_timeline_weeks || "-") + " weeks",
      (data.timeline_recommendation_note || ""),
      "",
      "Week 1 schedule:",
      (data.current_week_schedule && data.current_week_schedule.chapter) ? data.current_week_schedule.chapter + " – " + (data.current_week_schedule.focus || "") : "-",
      "",
      "Tasks this week:",
      ...(data.current_week_tasks || []).map((t) => "  • " + (t.title || t.chapter)),
    ];
    if (el("authResultPre")) el("authResultPre").textContent = lines.join("\n");
    showAuthPanel("result");
    if (el("authDiagnosticError")) el("authDiagnosticError").classList.add("hidden");
  } catch (err) {
    if (el("authDiagnosticError")) { el("authDiagnosticError").textContent = err.message || "Submit failed."; el("authDiagnosticError").classList.remove("hidden"); }
  }
}

function initApp() {
  initAuthTabs();
  const loginBtn = el("loginBtn");
  const signupBtn = el("signupBtn");
  const submitDiagBtn = el("authSubmitDiagnosticBtn");
  const goDashBtn = el("authGoDashboardBtn");
  const logoutBtn = el("logoutBtn");
  if (loginBtn) loginBtn.addEventListener("click", doLogin);
  if (signupBtn) signupBtn.addEventListener("click", doSignup);
  if (submitDiagBtn) submitDiagBtn.addEventListener("click", submitAuthDiagnostic);
  if (goDashBtn) goDashBtn.addEventListener("click", function () { showApp(); });
  if (logoutBtn) logoutBtn.addEventListener("click", function () { clearAuth(); showAuthGate(); });

  if (getAuthToken() && getStoredLearnerId()) {
    showApp();
  } else {
    showAuthGate();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

// Onboarding & Plan (diagnostic wizard state — used only for programmatic API tests; dashboard uses auth-gate flow)
let _obAttemptId = null;
let _obQuestions = [];

function renderObQuestions() {
  const container = el("obQuestionsContainer");
  if (!container) return;
  if (!_obQuestions.length) {
    container.innerHTML = "<p class=\"muted\">Start onboarding above to load questions.</p>";
    if (el("obSubmitDiagnosticRow")) el("obSubmitDiagnosticRow").style.display = "none";
    if (el("obSubmitDiagnosticActions")) el("obSubmitDiagnosticActions").style.display = "none";
    return;
  }
  container.innerHTML = "";
  const questions = _obQuestions.slice(0, 25);
  questions.forEach((q, idx) => {
    const block = document.createElement("div");
    block.className = "q-block";
    const lab = document.createElement("p");
    lab.className = "q-prompt";
    lab.textContent = (idx + 1) + ". " + (q.prompt || "Question");
    block.appendChild(lab);

    if ((q.question_type === "mcq" || q.question_type === "true_false") && q.options && q.options.length) {
      const opts = q.options.slice(0, q.question_type === "true_false" ? 2 : 4);
      const labels = ["A", "B", "C", "D"];
      opts.forEach((opt, optIdx) => {
        const optId = "ob-q-" + idx + "-opt-" + optIdx;
        const wrapper = document.createElement("label");
        wrapper.className = "q-option";

        const input = document.createElement("input");
        input.type = "radio";
        input.name = "ob-q-" + idx;
        input.id = optId;
        input.value = opt;

        const span = document.createElement("span");
        const letter = labels[optIdx] || "";
        span.textContent = (letter ? letter + ". " : "") + opt;

        wrapper.appendChild(input);
        wrapper.appendChild(span);
        block.appendChild(wrapper);
      });
    } else {
      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = "Your answer";
      input.id = "ob-a-" + idx;
      block.appendChild(input);
    }

    container.appendChild(block);
  });
  if (el("obSubmitDiagnosticRow")) el("obSubmitDiagnosticRow").style.display = "block";
  if (el("obSubmitDiagnosticActions")) el("obSubmitDiagnosticActions").style.display = "block";
}

async function onboardingStart() {
  const name = (el("obName") && el("obName").value.trim()) || "Test Learner";
  const grade_level = (el("obGrade") && el("obGrade").value.trim()) || "10";
  const selected_timeline_weeks = parseInt((el("obTimeline") && el("obTimeline").value) || "16", 10);
  try {
    const data = await apiCallOb("/onboarding/start", "POST", {
      name,
      grade_level,
      exam_in_months: 10,
      selected_timeline_weeks,
    });
    if (data.learner_id) el("obLearnerId").textContent = data.learner_id;
    _obAttemptId = data.diagnostic_attempt_id || null;
    _obQuestions = (data.questions || []).slice(0, 25);
    renderObQuestions();
    if (el("obDiagnosticResult")) el("obDiagnosticResult").style.display = "none";
    el("obResult").textContent = "Onboarding started. Learner ID: " + data.learner_id + "\nQuestions: " + (_obQuestions.length) + " items. Complete the diagnostic below and submit.";
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
  }
}

async function submitDiagnostic() {
  const learnerId = getObLearnerId();
  if (!_obAttemptId || !_obQuestions.length) {
    el("obDiagnosticResultPre").textContent = "Start onboarding and load questions first.";
    if (el("obDiagnosticResult")) el("obDiagnosticResult").style.display = "block";
    return;
  }
  const time_spent_minutes = parseInt((el("obTimeSpent") && el("obTimeSpent").value) || "15", 10);
  const answers = _obQuestions.slice(0, 25).map((q, idx) => {
    let value = "";
    if (q.question_type === "mcq" || q.question_type === "true_false") {
      const selected = document.querySelector('input[name="ob-q-' + idx + '"]:checked');
      value = (selected && selected.value) ? selected.value.trim() : "";
    } else {
      const input = el("ob-a-" + idx);
      value = (input && input.value) ? input.value.trim() : "";
    }
    return { question_id: q.question_id, answer: value };
  });
  try {
    const data = await apiCallOb("/onboarding/submit", "POST", {
      learner_id: learnerId,
      diagnostic_attempt_id: _obAttemptId,
      answers,
      time_spent_minutes,
    });
    const summary = "Score: " + (data.score != null ? (data.score * 100).toFixed(1) + "%" : "-") +
      "\nSelected timeline: " + (data.selected_timeline_weeks || "-") + " weeks" +
      "\nRecommended: " + (data.recommended_timeline_weeks || "-") + " weeks" +
      "\nCurrent forecast: " + (data.current_forecast_weeks || "-") + " weeks" +
      "\nNote: " + (data.timeline_recommendation_note || "-") +
      "\n\nFull response:\n" + JSON.stringify(data, null, 2);
    el("obDiagnosticResultPre").textContent = summary;
    if (el("obDiagnosticResult")) el("obDiagnosticResult").style.display = "block";
    el("obResult").textContent = "Diagnostic submitted. Score: " + (data.score != null ? (data.score * 100).toFixed(1) + "%" : "-");
  } catch (err) {
    el("obDiagnosticResultPre").textContent = "Error: " + err.message;
    if (el("obDiagnosticResult")) el("obDiagnosticResult").style.display = "block";
  }
}

function getObLearnerId() {
  const id = el("obLearnerId") && el("obLearnerId").textContent.trim();
  if (!id || id === "-") throw new Error("Start onboarding first to get a learner ID");
  return id;
}

async function fetchPlan() {
  try {
    const data = await apiCallOb("/onboarding/plan/" + getObLearnerId());
    el("obResult").textContent = JSON.stringify(data, null, 2);
    const sel = data.selected_timeline_weeks;
    const fcast = data.current_forecast_weeks;
    const delta = data.timeline_delta_weeks;
    const row = el("obTimelineSummaryRow");
    const summary = el("obTimelineSummary");
    if (row && summary && (sel != null || fcast != null)) {
      const d = delta != null ? delta : (fcast != null && sel != null ? fcast - sel : null);
      let hint = "";
      if (d != null) {
        if (d < 0) hint = " (ahead of goal)";
        else if (d > 0) hint = " (behind goal)";
        else hint = " (on track)";
      }
      summary.textContent = "Selected: " + (sel != null ? sel : "-") + " weeks | Forecast: " + (fcast != null ? fcast : "-") + " weeks | Delta: " + (d != null ? d : "-") + " weeks" + hint;
      row.style.display = "block";
    }
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
    if (el("obTimelineSummaryRow")) el("obTimelineSummaryRow").style.display = "none";
  }
}

async function fetchTasks() {
  try {
    const data = await apiCallOb("/onboarding/tasks/" + getObLearnerId());
    el("obResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
  }
}

async function fetchWhereIStand() {
  try {
    const data = await apiCallOb("/onboarding/where-i-stand/" + getObLearnerId());
    el("obResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
  }
}

async function fetchRevisionQueue() {
  try {
    const data = await apiCallOb("/onboarding/revision-queue/" + getObLearnerId());
    el("obResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
  }
}

async function fetchStreakSummary() {
  try {
    const id = getObLearnerId();
    const [metrics, engagement] = await Promise.all([
      apiCallOb("/onboarding/learning-metrics/" + id).catch(() => ({})),
      apiCallOb("/onboarding/engagement/summary/" + id).catch(() => ({})),
    ]);
    const parts = [];
    if (metrics.login_streak_days != null) parts.push("Login streak: " + metrics.login_streak_days + " days");
    if (engagement.login_streak_days != null && !parts.some(function(p) { return p.startsWith("Login streak"); })) parts.push("Login streak: " + engagement.login_streak_days + " days");
    if (metrics.adherence_rate_week != null) parts.push("Adherence (week): " + (metrics.adherence_rate_week * 100).toFixed(0) + "%");
    if (engagement.adherence_rate_week != null && !parts.some(p => p.startsWith("Adherence"))) parts.push("Adherence (week): " + (engagement.adherence_rate_week * 100).toFixed(0) + "%");
    if (metrics.confidence_score != null) parts.push("Confidence: " + (metrics.confidence_score * 100).toFixed(0) + "%");
    if (metrics.timeline_adherence_weeks != null) parts.push("Timeline adherence: " + metrics.timeline_adherence_weeks + " weeks");
    if (metrics.forecast_drift_weeks != null) parts.push("Forecast drift: " + metrics.forecast_drift_weeks + " weeks");
    if (engagement.engagement_minutes_week != null) parts.push("Minutes this week: " + engagement.engagement_minutes_week);
    const text = parts.length ? parts.join(" · ") : (metrics.avg_mastery_score != null ? "Avg mastery: " + (metrics.avg_mastery_score * 100).toFixed(0) + "%" : "No data yet.");
    el("obStreakSummary").textContent = text;
    el("obStreakSummaryRow").style.display = "block";
  } catch (err) {
    el("obStreakSummary").textContent = "Error: " + err.message;
    el("obStreakSummaryRow").style.display = "block";
  }
}

if (el("obStartBtn")) el("obStartBtn").addEventListener("click", onboardingStart);
if (el("obSubmitDiagnosticBtn")) el("obSubmitDiagnosticBtn").addEventListener("click", submitDiagnostic);
if (el("obPlanBtn")) el("obPlanBtn").addEventListener("click", fetchPlan);
if (el("obTasksBtn")) el("obTasksBtn").addEventListener("click", fetchTasks);
function masteryLevel(score) {
  if (score == null || typeof score !== "number") return "—";
  if (score < 0.4) return "Beginner";
  if (score < 0.6) return "Developing";
  if (score < 0.8) return "Proficient";
  return "Mastered";
}

async function fetchChapterTracker() {
  try {
    const data = await apiCallOb("/onboarding/where-i-stand/" + getObLearnerId());
    const status = data.chapter_status || [];
    const lines = status.map(function(s) {
      const ch = s.chapter || s.name || "?";
      const level = s.band || masteryLevel(s.score != null ? s.score : (s.mastery != null ? s.mastery : null));
      return ch + ": " + level;
    });
    el("obChapterTrackerText").textContent = lines.length ? lines.join(" · ") : "No chapter data yet.";
    el("obChapterTrackerRow").style.display = "block";
  } catch (err) {
    el("obChapterTrackerText").textContent = "Error: " + err.message;
    el("obChapterTrackerRow").style.display = "block";
  }
}

async function fetchConceptMap() {
  try {
    const data = await apiCallOb("/onboarding/where-i-stand/" + getObLearnerId());
    const strengths = (data.concept_strengths || []).slice(0, 8);
    const weaknesses = (data.concept_weaknesses || []).slice(0, 8);
    const conf = data.confidence_score != null ? (data.confidence_score * 100).toFixed(0) + "%" : "—";
    const parts = ["Confidence: " + conf];
    if (strengths.length) parts.push("Strengths: " + strengths.join(", "));
    if (weaknesses.length) parts.push("Weaknesses: " + weaknesses.join(", "));
    el("obConceptMapText").textContent = parts.join(" · ");
    el("obConceptMapRow").style.display = "block";
  } catch (err) {
    el("obConceptMapText").textContent = "Error: " + err.message;
    el("obConceptMapRow").style.display = "block";
  }
}

async function fetchNextWeek() {
  try {
    const data = await apiCallOb("/onboarding/plan/" + getObLearnerId());
    const rough = data.rough_plan || [];
    const next = rough[1] || rough[0];
    if (next) {
      el("obNextWeekText").textContent = "Week " + (next.week || "?") + ": " + (next.chapter || "—") + " — " + (next.focus || "");
    } else {
      el("obNextWeekText").textContent = "No next-week plan yet. Complete onboarding and get plan.";
    }
    el("obNextWeekRow").style.display = "block";
  } catch (err) {
    el("obNextWeekText").textContent = "Error: " + err.message;
    el("obNextWeekRow").style.display = "block";
  }
}

async function fetchForecastTrend() {
  try {
    const data = await apiCallOb("/onboarding/forecast-history/" + getObLearnerId());
    const history = data.history || [];
    const lines = history.map(function(h) {
      const d = h.generated_at ? new Date(h.generated_at).toLocaleDateString() : "";
      return "Week " + (h.week_number || "?") + ": forecast " + (h.current_forecast_weeks != null ? h.current_forecast_weeks : "—") + " wks, delta " + (h.timeline_delta_weeks != null ? (h.timeline_delta_weeks >= 0 ? "+" : "") + h.timeline_delta_weeks : "—") + " · " + (h.pacing_status || "") + (d ? " (" + d + ")" : "");
    });
    el("obForecastTrendText").textContent = lines.length ? lines.join("\n") : "No forecast history yet.";
    el("obForecastTrendRow").style.display = "block";
  } catch (err) {
    el("obForecastTrendText").textContent = "Error: " + err.message;
    el("obForecastTrendRow").style.display = "block";
  }
}

if (el("obStandBtn")) el("obStandBtn").addEventListener("click", fetchWhereIStand);
if (el("obRevisionQueueBtn")) el("obRevisionQueueBtn").addEventListener("click", fetchRevisionQueue);
if (el("obStreakBtn")) el("obStreakBtn").addEventListener("click", fetchStreakSummary);
if (el("obChapterTrackerBtn")) el("obChapterTrackerBtn").addEventListener("click", fetchChapterTracker);
if (el("obConceptMapBtn")) el("obConceptMapBtn").addEventListener("click", fetchConceptMap);
if (el("obNextWeekBtn")) el("obNextWeekBtn").addEventListener("click", fetchNextWeek);
if (el("obForecastTrendBtn")) el("obForecastTrendBtn").addEventListener("click", fetchForecastTrend);

// Admin
async function adminHealth() {
  try {
    const data = await apiCallAdmin("/health");
    el("adminResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("adminResult").textContent = "Error: " + err.message;
  }
}

async function adminMetrics() {
  try {
    const data = await apiCallAdmin("/metrics/app");
    el("adminResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("adminResult").textContent = "Error: " + err.message;
  }
}

async function adminGrounding() {
  try {
    const data = await apiCallAdmin("/grounding/status");
    el("adminResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("adminResult").textContent = "Error: " + err.message;
  }
}

async function adminCohort() {
  try {
    const data = await apiCallAdmin("/admin/cohort?include_list=true");
    el("adminResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("adminResult").textContent = "Error: " + err.message;
  }
}

async function adminViolations() {
  try {
    const data = await apiCallAdmin("/admin/policy-violations");
    el("adminResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("adminResult").textContent = "Error: " + err.message;
  }
}

async function adminDrift() {
  try {
    const data = await apiCallAdmin("/admin/timeline-drift");
    el("adminResult").textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    el("adminResult").textContent = "Error: " + err.message;
  }
}

if (el("adminHealthBtn")) el("adminHealthBtn").addEventListener("click", adminHealth);
if (el("adminMetricsBtn")) el("adminMetricsBtn").addEventListener("click", adminMetrics);
if (el("adminGroundingBtn")) el("adminGroundingBtn").addEventListener("click", adminGrounding);
if (el("adminCohortBtn")) el("adminCohortBtn").addEventListener("click", adminCohort);
if (el("adminViolationsBtn")) el("adminViolationsBtn").addEventListener("click", adminViolations);
if (el("adminDriftBtn")) el("adminDriftBtn").addEventListener("click", adminDrift);
