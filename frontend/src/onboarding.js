/**
 * Mentorix — Onboarding Module (ES Module)
 * Handles diagnostic test, signup flow, and onboarding completion.
 */
import { api, setAuth, setApiBase, getApiBase } from "./auth.js";
import { $, show, hide } from "./helpers.js";

let diagnosticData = null;
let diagnosticTimer = null;
let diagnosticSeconds = 1800; // 30 minutes

/**
 * Start the diagnostic timer countdown.
 */
export function startDiagnosticTimer() {
  diagnosticSeconds = 1800;
  const el = $("diagnostic-timer");
  if (diagnosticTimer) clearInterval(diagnosticTimer);
  diagnosticTimer = setInterval(() => {
    diagnosticSeconds--;
    if (el) el.textContent = formatTime(diagnosticSeconds);
    if (diagnosticSeconds <= 0) {
      clearInterval(diagnosticTimer);
      submitDiagnostic();
    }
  }, 1000);
}

/**
 * Render diagnostic questions into the test container.
 * @param {Array} questions - array of question objects from API
 */
export function renderDiagnosticQuestions(questions) {
  const container = $("test-questions");
  if (!container) return;
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
}

/**
 * Submit diagnostic answers and complete onboarding.
 */
export async function submitDiagnostic() {
  if (!diagnosticData) return;
  if (diagnosticTimer) clearInterval(diagnosticTimer);

  const answers = {};
  diagnosticData.questions.forEach(q => {
    const selected = document.querySelector(`input[name="diag_${q.question_id}"]:checked`);
    answers[q.question_id] = selected ? parseInt(selected.value, 10) : -1;
  });

  try {
    const result = await api("/onboarding/submit-diagnostic", {
      method: "POST",
      body: {
        signup_draft_id: diagnosticData.signup_draft_id,
        diagnostic_attempt_id: diagnosticData.attempt_id,
        answers,
        time_taken_seconds: 1800 - diagnosticSeconds,
      },
    });
    return result;
  } catch (err) {
    console.error("[onboarding] submitDiagnostic error:", err);
    throw err;
  }
}

function formatTime(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export { diagnosticData, diagnosticTimer, diagnosticSeconds };
