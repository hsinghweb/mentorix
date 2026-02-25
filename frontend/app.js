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
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
  if (learnerId) localStorage.setItem(LEARNER_ID_KEY, learnerId);
  if (apiBase) localStorage.setItem(API_BASE_KEY, apiBase);
}
function clearAuth() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(LEARNER_ID_KEY);
}
function getAuthBaseUrl() {
  return (el("authApiBase") && el("authApiBase").value.trim().replace(/\/+$/, "")) || localStorage.getItem(API_BASE_KEY) || "http://localhost:8000";
}
function showAuthGate() {
  if (el("auth-gate")) el("auth-gate").classList.remove("hidden");
  if (el("app-main")) el("app-main").classList.add("hidden");
}
function showApp() {
  if (el("auth-gate")) el("auth-gate").classList.add("hidden");
  if (el("app-main")) el("app-main").classList.remove("hidden");
  const lid = getStoredLearnerId();
  const base = localStorage.getItem(API_BASE_KEY) || "http://localhost:8000";
  if (el("learnerId")) el("learnerId").value = lid;
  if (el("obLearnerId")) el("obLearnerId").textContent = lid;
  if (el("apiBase")) el("apiBase").value = base;
  if (el("obApiBase")) el("obApiBase").value = base;
}
function showAuthPanel(name) {
  ["auth-login", "auth-signup", "auth-diagnostic", "auth-result"].forEach((id) => {
    const p = el(id);
    if (p) p.classList.toggle("hidden", id !== "auth-" + name);
  });
}

function logStatus(message, data) {
  const stamp = new Date().toLocaleTimeString();
  const suffix = data ? `\n${JSON.stringify(data, null, 2)}` : "";
  el("status").textContent = `[${stamp}] ${message}${suffix}`;
}

function newUuid() {
  return crypto.randomUUID();
}

function getBaseUrl() {
  return el("apiBase").value.trim().replace(/\/+$/, "");
}

function getObBaseUrl() {
  return (el("obApiBase") && el("obApiBase").value.trim().replace(/\/+$/, "")) || getBaseUrl();
}

function getAdminBaseUrl() {
  return (el("adminApiBase") && el("adminApiBase").value.trim().replace(/\/+$/, "")) || getBaseUrl();
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
let _authDiagnosticAttemptId = null;
let _authDiagnosticQuestions = [];

document.querySelectorAll("#auth-tabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const auth = btn.getAttribute("data-auth");
    if (!auth) return;
    document.querySelectorAll("#auth-tabs .tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    showAuthPanel(auth);
    if (el("authLoginError")) el("authLoginError").classList.add("hidden");
    if (el("authSignupError")) el("authSignupError").classList.add("hidden");
  });
});

async function doLogin() {
  const username = (el("loginUsername") && el("loginUsername").value.trim()) || "";
  const password = (el("loginPassword") && el("loginPassword").value) || "";
  const base = getAuthBaseUrl();
  if (!username || !password) {
    if (el("authLoginError")) { el("authLoginError").textContent = "Username and password required."; el("authLoginError").classList.remove("hidden"); }
    return;
  }
  try {
    const resp = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || resp.statusText);
    setAuth(data.token, data.learner_id, base);
    showApp();
  } catch (err) {
    if (el("authLoginError")) { el("authLoginError").textContent = err.message || "Login failed."; el("authLoginError").classList.remove("hidden"); }
  }
}

async function doSignup() {
  const username = (el("signupUsername") && el("signupUsername").value.trim()) || "";
  const password = (el("signupPassword") && el("signupPassword").value) || "";
  const name = (el("signupName") && el("signupName").value.trim()) || "";
  const date_of_birth = (el("signupDob") && el("signupDob").value) || "";
  const selected_timeline_weeks = parseInt((el("signupWeeks") && el("signupWeeks").value) || "28", 10);
  const base = getAuthBaseUrl();
  if (!username || !password || !name || !date_of_birth) {
    if (el("authSignupError")) { el("authSignupError").textContent = "All fields required."; el("authSignupError").classList.remove("hidden"); }
    return;
  }
  try {
    const resp = await fetch(`${base}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, name, date_of_birth, selected_timeline_weeks }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || resp.statusText);
    setAuth(data.token, data.learner_id, base);
    _authDiagnosticAttemptId = null;
    _authDiagnosticQuestions = [];
    const qResp = await fetch(`${base}/onboarding/diagnostic-questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ learner_id: data.learner_id }),
    });
    const qData = await qResp.json();
    if (!qResp.ok) throw new Error(qData.detail || "Could not load diagnostic questions.");
    _authDiagnosticAttemptId = qData.diagnostic_attempt_id;
    _authDiagnosticQuestions = qData.questions || [];
    renderAuthDiagnosticQuestions();
    showAuthPanel("diagnostic");
    if (el("authDiagnosticError")) el("authDiagnosticError").classList.add("hidden");
  } catch (err) {
    if (el("authSignupError")) { el("authSignupError").textContent = err.message || "Signup failed."; el("authSignupError").classList.remove("hidden"); }
  }
}

function renderAuthDiagnosticQuestions() {
  const container = el("authQuestionsContainer");
  if (!container || !_authDiagnosticQuestions.length) return;
  container.innerHTML = "";
  _authDiagnosticQuestions.forEach((q, idx) => {
    const block = document.createElement("div");
    block.className = "q-block";
    const lab = document.createElement("label");
    lab.className = "q-prompt";
    lab.textContent = (idx + 1) + ". " + (q.prompt || "Question");
    block.appendChild(lab);
    const sel = document.createElement("select");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "-- choose --";
    sel.appendChild(empty);
    (q.options || []).forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt;
      o.textContent = opt;
      sel.appendChild(o);
    });
    sel.setAttribute("data-question-id", q.question_id);
    sel.id = "auth-q-" + idx;
    block.appendChild(sel);
    container.appendChild(block);
  });
}

async function submitAuthDiagnostic() {
  const learnerId = getStoredLearnerId();
  const base = getAuthBaseUrl();
  if (!_authDiagnosticAttemptId || !_authDiagnosticQuestions.length || !learnerId) {
    if (el("authDiagnosticError")) { el("authDiagnosticError").textContent = "Complete the test first."; el("authDiagnosticError").classList.remove("hidden"); }
    return;
  }
  const answers = _authDiagnosticQuestions.map((q, idx) => {
    const sel = el("auth-q-" + idx);
    return { question_id: q.question_id, answer: (sel && sel.value) ? sel.value.trim() : "" };
  });
  try {
    const resp = await fetch(`${base}/onboarding/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        learner_id: learnerId,
        diagnostic_attempt_id: _authDiagnosticAttemptId,
        answers,
        time_spent_minutes: 15,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || resp.statusText);
    const lines = [
      "Score: " + (data.score != null ? (data.score * 100).toFixed(1) + "%" : "-"),
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

if (el("loginBtn")) el("loginBtn").addEventListener("click", doLogin);
if (el("signupBtn")) el("signupBtn").addEventListener("click", doSignup);
if (el("authSubmitDiagnosticBtn")) el("authSubmitDiagnosticBtn").addEventListener("click", submitAuthDiagnostic);
if (el("authGoDashboardBtn")) el("authGoDashboardBtn").addEventListener("click", () => { showApp(); });
if (el("logoutBtn")) el("logoutBtn").addEventListener("click", () => { clearAuth(); showAuthGate(); });

if (getAuthToken() && getStoredLearnerId()) {
  showApp();
} else {
  showAuthGate();
}

// Tabs (main app only)
document.querySelectorAll("#app-main nav.tabs .tab[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.getAttribute("data-tab");
    if (!tab) return;
    document.querySelectorAll("#app-main nav.tabs .tab[data-tab]").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll("#app-main .panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    const panel = document.getElementById("panel-" + tab);
    if (panel) panel.classList.remove("hidden");
  });
});

// Onboarding & Plan (diagnostic wizard state)
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
  _obQuestions.forEach((q, idx) => {
    const block = document.createElement("div");
    block.className = "q-block";
    const lab = document.createElement("label");
    lab.className = "q-prompt";
    lab.textContent = (idx + 1) + ". " + (q.prompt || "Question");
    block.appendChild(lab);
    let input;
    if (q.question_type === "mcq" && q.options && q.options.length) {
      input = document.createElement("select");
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "-- choose --";
      input.appendChild(empty);
      q.options.forEach((opt) => {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        input.appendChild(o);
      });
    } else if (q.question_type === "true_false") {
      input = document.createElement("select");
      ["", "true", "false"].forEach((v) => {
        const o = document.createElement("option");
        o.value = v;
        o.textContent = v || "-- choose --";
        input.appendChild(o);
      });
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.placeholder = "Your answer";
    }
    input.setAttribute("data-question-id", q.question_id);
    input.id = "ob-a-" + idx;
    block.appendChild(input);
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
    _obQuestions = data.questions || [];
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
  const answers = _obQuestions.map((q, idx) => {
    const input = el("ob-a-" + idx);
    return { question_id: q.question_id, answer: (input && input.value) ? input.value.trim() : "" };
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

if (!el("learnerId").value) {
  el("learnerId").value = newUuid();
}
