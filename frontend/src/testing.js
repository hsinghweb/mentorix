/**
 * Mentorix — Testing Module (ES Module)
 * Handles chapter test loading, rendering, submission, and timer.
 */
import { api, getLearnerId } from "./auth.js";
import { $, show, hide, formatTime } from "./helpers.js";

let testTimer = null;
let testSeconds = 1200; // 20 minutes
let currentTestData = null;

/**
 * Start a chapter test.
 * @param {number} chapterNumber - Chapter number to test
 */
export async function startChapterTest(chapterNumber) {
  const learnerId = getLearnerId();
  if (!learnerId) return;

  try {
    const data = await api(`/learning/chapter-test/${chapterNumber}?learner_id=${learnerId}`);
    currentTestData = {
      test_id: data.test_id,
      questions: data.questions,
      chapter: data.chapter,
      chapter_number: chapterNumber,
    };
    renderTestQuestions(data.questions);
    startTestTimer();
    return data;
  } catch (err) {
    console.error("[testing] startChapterTest error:", err);
    throw err;
  }
}

/**
 * Render test questions into the UI.
 * @param {Array} questions - Questions returned from the API
 */
export function renderTestQuestions(questions) {
  const container = $("chapter-test-questions");
  if (!container) return;
  container.innerHTML = "";

  questions.forEach((q, i) => {
    const card = document.createElement("div");
    card.className = "question-card";
    card.id = `test-q-${q.question_id || i}`;
    card.innerHTML = `
      <div class="question-number">Question ${i + 1} of ${questions.length}</div>
      <div class="question-prompt">${q.prompt}</div>
      <div class="question-options">
        ${(q.options || []).map((opt, oi) => `
          <label class="option-label" data-qid="${q.question_id || i}" data-idx="${oi}">
            <input type="radio" name="test_${q.question_id || i}" value="${oi}">
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
 * Start the chapter test timer countdown.
 */
export function startTestTimer() {
  testSeconds = 1200;
  if (testTimer) clearInterval(testTimer);
  const el = $("test-timer");
  testTimer = setInterval(() => {
    testSeconds--;
    if (el) el.textContent = formatTime(testSeconds);
    if (testSeconds <= 0) {
      clearInterval(testTimer);
      submitChapterTest();
    }
  }, 1000);
}

/**
 * Submit chapter test answers to the backend.
 */
export async function submitChapterTest() {
  if (!currentTestData) return;
  if (testTimer) clearInterval(testTimer);

  const learnerId = getLearnerId();
  const answers = {};
  currentTestData.questions.forEach(q => {
    const qid = q.question_id || q.id;
    const selected = document.querySelector(`input[name="test_${qid}"]:checked`);
    answers[qid] = selected ? parseInt(selected.value, 10) : -1;
  });

  try {
    const result = await api("/learning/submit-chapter-test", {
      method: "POST",
      body: {
        learner_id: learnerId,
        test_id: currentTestData.test_id,
        chapter_number: currentTestData.chapter_number,
        answers,
        time_taken_seconds: 1200 - testSeconds,
      },
    });
    return result;
  } catch (err) {
    console.error("[testing] submitChapterTest error:", err);
    throw err;
  }
}

export { testTimer, testSeconds, currentTestData };
