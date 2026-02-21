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

if (!el("learnerId").value) {
  el("learnerId").value = newUuid();
}
