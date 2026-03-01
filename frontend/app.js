// API and auth storage keys
const TOKEN_KEY = "mentorix_token";
const LEARNER_KEY = "mentorix_learner_id";
const NAME_KEY = "mentorix_name";
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

// ── HELPERS ─────────────────────────────────────────────────────────────────
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function getLearnerId() { return localStorage.getItem(LEARNER_KEY); }
function setAuth(token, learnerId, name) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(LEARNER_KEY, learnerId);
  localStorage.setItem(NAME_KEY, name);
}
function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(LEARNER_KEY);
  localStorage.removeItem(NAME_KEY);
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

function renderKaTeX(container) {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(container, {
      delimiters: [
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
        { left: "$$", right: "$$", display: true },
      ],
      throwOnError: false,
    });
  }
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// Simple markdown-to-HTML conversion
function mdToHtml(md) {
  if (!md) return "";
  return md
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>")
    .replace(/^/, "<p>")
    .replace(/$/, "</p>")
    .replace(/<p><h/g, "<h")
    .replace(/<\/h(\d)><\/p>/g, "</h$1>")
    .replace(/<p><ul>/g, "<ul>")
    .replace(/<\/ul><\/p>/g, "</ul>")
    .replace(/<p><\/p>/g, "");
}


// ── INITIALIZATION ──────────────────────────────────────────────────────────
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
    const inp2 = $("api-base-url-signup");
    if (inp) inp.value = savedBase;
    if (inp2) inp2.value = savedBase;
  }
}

function bindEvents() {
  // Auth
  $("form-login").addEventListener("submit", handleLogin);
  $("form-signup").addEventListener("submit", handleSignup);
  $("link-to-signup").addEventListener("click", e => { e.preventDefault(); hide($("panel-login")); show($("panel-signup")); });
  $("link-to-login").addEventListener("click", e => { e.preventDefault(); hide($("panel-signup")); show($("panel-login")); });
  $("btn-logout").addEventListener("click", handleLogout);

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
}

function checkAuthState() {
  if (getToken() && getLearnerId()) {
    hide($("auth-gate"));
    show($("app-main"));
    $("nav-student-name").textContent = localStorage.getItem(NAME_KEY) || "Student";
    loadDashboard();
  }
}


// ── AUTH ─────────────────────────────────────────────────────────────────────
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
    setAuth(data.token, data.learner_id, data.name);
    hide($("auth-gate"));
    show($("app-main"));
    $("nav-student-name").textContent = data.name;
    loadDashboard();
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
  hide($("panel-diagnostic"));
  hide($("panel-result"));
  show($("panel-login"));
}


// ── DIAGNOSTIC ──────────────────────────────────────────────────────────────
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
            📅 You chose <strong>${result.selected_timeline_weeks} weeks</strong>.
            Based on your performance, we suggest <strong>${result.recommended_timeline_weeks} weeks</strong>.
            ${result.timeline_recommendation_note || ""}
        </div>
        ${chaptersHtml}
    `;
  renderKaTeX(container);
}


// ── DASHBOARD ───────────────────────────────────────────────────────────────
async function loadDashboard() {
  showScreen("dashboard");
  const learnerId = getLearnerId();
  $("nav-student-name").textContent = localStorage.getItem(NAME_KEY) || "Student";

  try {
    const data = await api(`/learning/dashboard/${learnerId}`);
    renderDashboard(data);
  } catch (err) {
    console.error("Dashboard load failed:", err);
    // Show a minimal dashboard if the learning endpoint fails
    try {
      // Try onboarding endpoint as fallback
      renderDashboardFallback();
    } catch (e2) {
      $("profile-card").innerHTML = `<div class="profile-stat"><div class="stat-value">⚠️</div><div class="stat-label">${err.message}</div></div>`;
    }
  }
}

function renderDashboard(data) {
  // Profile card
  $("profile-card").innerHTML = `
        <div class="profile-stat">
            <div class="stat-value">📐</div>
            <div class="stat-label">${data.student_name}</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">W${data.current_week}</div>
            <div class="stat-label">Current Week</div>
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
            <div class="stat-label">Diagnostic</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">${data.selected_weeks || "—"}/${data.suggested_weeks || "—"}</div>
            <div class="stat-label">Chosen / Suggested Wks</div>
        </div>
    `;

  // Current week tasks
  renderTasks(data.current_week_tasks, data.current_week);

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

  // Check if week is complete (all tasks done) → show advance button
  checkWeekComplete(data.current_week_tasks, data.learner_id);
}

function renderDashboardFallback() {
  $("profile-card").innerHTML = `
        <div class="profile-stat">
            <div class="stat-value">📐</div>
            <div class="stat-label">${localStorage.getItem(NAME_KEY) || "Student"}</div>
        </div>
        <div class="profile-stat">
            <div class="stat-value">—</div>
            <div class="stat-label">Loading...</div>
        </div>
    `;
}

function renderTasks(tasks, weekNumber) {
  const container = $("current-tasks");
  $("section-tasks").querySelector(".section-title").textContent = `📋 Week ${weekNumber} Tasks`;

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
          const icon = t.task_type === "read" ? "📖" : (isChapterLevel ? "📋" : "📝");
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
    const icon = t.task_type === "read" ? "📖" : (isChapterLevel ? "📋" : "📝");
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
                    🎉 All done! Advance to next week →
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
    if (btn) { btn.disabled = false; btn.textContent = "🎉 Advance to next week →"; }
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
                <div class="confidence-score">Score: ${pct}% • Attempts: ${ch.attempt_count}${ch.revision_queued ? " • 🔄 Revision" : ""}</div>
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
                    <div class="plan-week-chapter">${p.chapter}</div>
                    <div class="plan-week-focus">${p.focus || ""}</div>
                </div>
            </div>
        `;
  }).join("");
}

function renderRevision(revisions) {
  $("revision-list").innerHTML = revisions.map(r => `
        <div class="revision-item">
            <div class="revision-icon">🔄</div>
            <div class="revision-info">
                <div class="revision-chapter">${r.chapter}</div>
                <div class="revision-reason">${r.reason}</div>
            </div>
        </div>
    `).join("");
}


// ── READING ─────────────────────────────────────────────────────────────────
async function openReading(chapterNumber, taskId) {
  showScreen("reading");
  readingTaskId = taskId;
  readingChapterNumber = chapterNumber;
  readingSeconds = 0;

  $("reading-chapter-title").textContent = "Loading...";
  $("reading-content").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>Generating reading material from NCERT...</p></div>`;
  $("reading-status").className = "reading-status in-progress";
  $("reading-status").textContent = "📖 Keep reading... (min 3 minutes)";

  // Start timer
  $("reading-timer").textContent = "Time: 0:00";
  readingTimer = setInterval(() => {
    readingSeconds++;
    $("reading-timer").textContent = `Time: ${formatTime(readingSeconds)}`;

    if (readingSeconds >= 180) {
      $("reading-status").className = "reading-status complete";
      $("reading-status").textContent = "✅ Reading complete! You can go back to dashboard.";
      // Auto-complete the reading task
      completeReading();
    }
  }, 1000);

  try {
    const content = await api("/learning/content", {
      method: "POST",
      body: { learner_id: getLearnerId(), chapter_number: chapterNumber, regenerate: false },
    });

    const sourceBadge = content.source === "cached"
      ? `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">📦 CACHED</span>`
      : `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">✨ FRESH</span>`;
    $("reading-chapter-title").innerHTML = `📖 ${content.chapter_title} ${sourceBadge}`;
    $("reading-content").innerHTML = mdToHtml(content.content);
    renderKaTeX($("reading-content"));
    if (readingSeconds >= 180) {
      $("reading-status").className = "reading-status complete";
      $("reading-status").innerHTML = `
        ✅ Reading complete
        <button onclick="openReading(${chapterNumber}, ${taskId ? `'${taskId}'` : "null"})" style="margin-left:12px;padding:4px 12px;font-size:0.8rem;background:var(--warning);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">🔄 Reload</button>
        <button onclick="regenerateChapterReading(${chapterNumber}, ${taskId ? `'${taskId}'` : "null"})" style="margin-left:8px;padding:4px 12px;font-size:0.8rem;background:var(--info);color:white;border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">✨ Regenerate</button>
      `;
    }
  } catch (err) {
    $("reading-content").innerHTML = `<p style="color:var(--danger)">Error loading content: ${err.message}</p>`;
  }
}

async function completeReading() {
  if (!readingTaskId) return;
  try {
    await api("/learning/reading/complete", {
      method: "POST",
      body: {
        learner_id: getLearnerId(),
        task_id: readingTaskId,
        time_spent_seconds: readingSeconds,
      },
    });
  } catch (err) {
    console.warn("Reading completion failed:", err);
  }
}

function backToDashboard() {
  if (readingTimer) { clearInterval(readingTimer); readingTimer = null; }
  if (testTimer) { clearInterval(testTimer); testTimer = null; }
  showScreen("dashboard");
  loadDashboard();
}


// ── CHAPTER TEST ────────────────────────────────────────────────────────────
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
      sourceBadge = `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">🔄 REGENERATED</span>`;
    } else if (testResp.source === "cached") {
      sourceBadge = `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">📦 CACHED</span>`;
    } else {
      sourceBadge = `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">✨ FRESH</span>`;
    }
    $("test-chapter-title").innerHTML = `📝 Test: ${testResp.chapter} ${sourceBadge}`;
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
            <div class="question-prompt">${q.prompt}</div>
            <div class="question-options">
                ${q.options.map((opt, oi) => `
                    <label class="option-label" data-qid="${q.question_id}" data-idx="${oi}">
                        <input type="radio" name="chtest_${q.question_id}" value="${oi}">
                        <span class="option-indicator"></span>
                        <span>${opt}</span>
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
            <strong>Q${idx + 1}. ${q.prompt || q.question_id}</strong>
            <span class="task-status-badge ${state === "correct" ? "completed" : "pending"}">${state === "correct" ? "Correct" : "Wrong"}</span>
          </div>
          <div style="margin-top:6px;color:var(--text-secondary);font-size:0.9rem">Your answer: <strong>${selectedText}</strong></div>
          <div style="color:var(--text-secondary);font-size:0.9rem">Correct answer: <strong>${correctText}</strong></div>
          <div style="margin-top:8px">${explainBtn}</div>
          <div id="explain-${q.question_id}" style="margin-top:8px;color:var(--text-secondary);font-size:0.9rem"></div>
        </div>
      `;
    }).join("");

    feedbackEl.innerHTML = `
            <h3>${result.score >= 0.6 ? "🎉" : "💪"} Score: ${result.correct}/${result.total} (${(result.score * 100).toFixed(0)}%)</h3>
            <p>${result.message}</p>
            <div style="margin-top:14px; display:flex; gap:10px; justify-content:center;">
                <button class="btn btn-primary" onclick="${retakeAction}">🔄 Retake Test</button>
                <button class="btn btn-outline" onclick="${regenerateAction}">✨ Regenerate</button>
                <button class="btn btn-secondary" onclick="backToDashboard()">← Dashboard</button>
            </div>
            <div style="margin-top:14px;text-align:left">
              <h4 style="margin-bottom:8px">Question Review</h4>
              ${questionReviewHtml || `<p style="color:var(--text-muted)">Question-wise review is unavailable for this attempt.</p>`}
            </div>
        `;

    $("btn-submit-chapter-test").textContent = "Submit Test";
  } catch (err) {
    alert("Error submitting test: " + err.message);
    $("btn-submit-chapter-test").disabled = false;
    $("btn-submit-chapter-test").textContent = "Submit Test";
  }
}


// ── CHAPTER DETAIL DRILL-DOWN ───────────────────────────────────────────────
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
      const readIcon = s.reading_completed ? "✅" : "⬜";
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
        <h3 style="margin-bottom:6px;color:var(--text-primary);font-size:1.25rem">📚 Ch ${chapterNumber}: ${data.chapter_title}</h3>
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
  readingChapterNumber = chapterNumber;
  readingSeconds = 0;
  readingTaskId = taskId;

  $("reading-chapter-title").textContent = regenerate ? "Regenerating section content..." : "Loading section content...";
  $("reading-content").innerHTML = `<div class="loading-overlay"><div class="loading-spinner"></div><p>${regenerate ? "Regenerating fresh content from NCERT..." : "Loading section reading material..."}</p></div>`;
  $("reading-status").className = "reading-status in-progress";
  $("reading-status").textContent = taskId ? "📖 Keep reading... (min 3 minutes)" : "📖 Reading section content...";

  $("reading-timer").textContent = "Time: 0:00";
  let sectionTaskCompleted = false;
  readingTimer = setInterval(() => {
    readingSeconds++;
    $("reading-timer").textContent = `Time: ${formatTime(readingSeconds)}`;
    if (taskId && !sectionTaskCompleted && readingSeconds >= 180) {
      sectionTaskCompleted = true;
      completeReading();
      $("reading-status").className = "reading-status complete";
      $("reading-status").innerHTML = `
        📖 Reading complete
        <button onclick="openSectionReading(${chapterNumber}, '${sectionId}', true, ${taskId ? `'${taskId}'` : "null"})" style="margin-left:12px;padding:4px 12px;font-size:0.8rem;background:var(--warning);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">🔄 Regenerate</button>
        <button onclick="showScreen('dashboard');loadDashboard()" style="margin-left:8px;padding:4px 12px;font-size:0.8rem;background:var(--bg-elevated);color:var(--text-secondary);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer">← Dashboard</button>
      `;
    }
  }, 1000);

  try {
    const content = await api("/learning/content/section", {
      method: "POST",
      body: { learner_id: getLearnerId(), chapter_number: chapterNumber, section_id: sectionId, regenerate },
    });

    const sourceBadge = content.source === "cached"
      ? `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">📦 CACHED</span>`
      : `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">✨ FRESH</span>`;

    $("reading-chapter-title").innerHTML = `📖 ${content.section_id} - ${content.section_title} ${sourceBadge}`;
    $("reading-content").innerHTML = mdToHtml(content.content);
    renderKaTeX($("reading-content"));

    if (!taskId) {
      $("reading-status").className = "reading-status complete";
      $("reading-status").innerHTML = `
        📖 Reading complete
        <button onclick="openSectionReading(${chapterNumber}, '${sectionId}', true, ${taskId ? `'${taskId}'` : "null"})" style="margin-left:12px;padding:4px 12px;font-size:0.8rem;background:var(--warning);color:var(--bg-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;font-weight:600">🔄 Regenerate</button>
        <button onclick="showScreen('dashboard');loadDashboard()" style="margin-left:8px;padding:4px 12px;font-size:0.8rem;background:var(--bg-elevated);color:var(--text-secondary);border:1px solid var(--border);border-radius:var(--radius-sm);cursor:pointer">← Dashboard</button>
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
      ? `<span style="display:inline-block;padding:2px 8px;background:var(--success-light);color:var(--success);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">📦 CACHED</span>`
      : `<span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">✨ FRESH</span>`;

    $("test-chapter-title").innerHTML = `📝 ${testResp.section_id} - ${testResp.section_title} ${sourceBadge}`;
    renderChapterTestQuestions(testResp.questions);
    startChapterTestTimer();
  } catch (err) {
    $("chapter-test-questions").innerHTML = `<p style="color:var(--danger)">Error generating section test: ${err.message}</p>`;
  }
}


// ── SCREEN MANAGEMENT ───────────────────────────────────────────────────────────────────
function showScreen(screenName) {
  document.querySelectorAll(".screen").forEach(s => s.classList.add("hidden"));
  const screen = $(`screen-${screenName}`);
  if (screen) screen.classList.remove("hidden");
}


// ── DAILY PLAN ────────────────────────────────────────────────────────────────────────
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
        const icon = t.task_type === "read" ? "📖" : (t.chapter_level ? "📋" : "📝");
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
    container.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-muted)">✨ All caught up! No pending tasks for today.</div>`;
    return;
  }

  container.innerHTML = todayTasks.map((t, i) => {
    const icon = t.task_type === "read" ? "📖" : (t.chapter_level ? "📋" : "📝");
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
      body: { learner_id: getLearnerId(), chapter_number: chapterNumber, regenerate: true },
    });
    $("reading-chapter-title").innerHTML = `📖 ${content.chapter_title} <span style="display:inline-block;padding:2px 8px;background:var(--info-light);color:var(--info);border-radius:12px;font-size:0.7rem;font-weight:600;margin-left:8px">🔄 REGENERATED</span>`;
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
    const source = resp.source === "cached" ? "📦 cached" : "✨ generated";
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
        <div class="revision-icon">🕒</div>
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
    const arrow = trend.trend === "up" ? "↗" : (trend.trend === "down" ? "↘" : "→");
    const latest = ((trend.latest_score || 0) * 100).toFixed(0);
    const n = (trend.points || []).length;
    el.textContent = `${arrow} Confidence trend: ${trend.trend} • Latest ${latest}% • ${n} attempts tracked`;
  } catch (err) {
    el.textContent = "Confidence trend unavailable";
  }
}


// ── PRACTICE QUESTIONS ────────────────────────────────────────────────────────────────
let practiceData = null;

async function openPractice(chapterNumber, sectionId) {
  showScreen("practice");
  $("practice-title").textContent = `📝 Practice: §${sectionId}`;
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
        resultDiv.textContent = "✅ Correct!";
      } else {
        resultDiv.style.background = "var(--danger-light)";
        resultDiv.style.color = "var(--danger)";
        resultDiv.textContent = `❌ Incorrect. Answer: ${(q.options || [])[correctIdx] || "N/A"}`;
      }
    }
  });
  const total = practiceData.questions.length;
  const pct = ((correct / total) * 100).toFixed(0);
  const fb = $("practice-feedback");
  show(fb);
  fb.innerHTML = `<div style="text-align:center;padding:16px"><h3>🎯 ${correct}/${total} (${pct}%)</h3><p>${correct === total ? "🌟 Perfect!" : correct >= total * 0.6 ? "👍 Good job!" : "💪 Keep practicing!"}</p></div>`;
  $("btn-check-practice").disabled = true;
}
