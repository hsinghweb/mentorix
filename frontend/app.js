function el(id) {
  return document.getElementById(id);
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

// Tabs
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tab = btn.getAttribute("data-tab");
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    const panel = document.getElementById("panel-" + tab);
    if (panel) panel.classList.remove("hidden");
  });
});

// Onboarding & Plan
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
    el("obResult").textContent = "Onboarding started. Learner ID: " + data.learner_id + "\nQuestions: " + (data.questions && data.questions.length) + " items.";
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
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
  } catch (err) {
    el("obResult").textContent = "Error: " + err.message;
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

if (el("obStartBtn")) el("obStartBtn").addEventListener("click", onboardingStart);
if (el("obPlanBtn")) el("obPlanBtn").addEventListener("click", fetchPlan);
if (el("obTasksBtn")) el("obTasksBtn").addEventListener("click", fetchTasks);
if (el("obStandBtn")) el("obStandBtn").addEventListener("click", fetchWhereIStand);

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

if (el("adminHealthBtn")) el("adminHealthBtn").addEventListener("click", adminHealth);
if (el("adminMetricsBtn")) el("adminMetricsBtn").addEventListener("click", adminMetrics);
if (el("adminGroundingBtn")) el("adminGroundingBtn").addEventListener("click", adminGrounding);

if (!el("learnerId").value) {
  el("learnerId").value = newUuid();
}
