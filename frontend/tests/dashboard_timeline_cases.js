const fs = require("fs");
const path = require("path");

const appJsPath = path.resolve(__dirname, "..", "app.js");
const content = fs.readFileSync(appJsPath, "utf8");

function assertContains(pattern, message) {
  if (!pattern.test(content)) {
    throw new Error(message);
  }
}

function assertNotContains(pattern, message) {
  if (pattern.test(content)) {
    throw new Error(message);
  }
}

// UI regression guard: dashboard must show scheduled completion date.
assertContains(/completion_estimate_date\)/, "Missing scheduled completion date rendering.");
assertContains(/Scheduled Completion/, "Missing scheduled completion label.");

// Active Pace ETA was intentionally removed (Section 12.1) — verify it stays removed.
assertNotContains(/Active Pace ETA/, "Active Pace ETA should have been removed from dashboard.");

console.log("dashboard_timeline_cases: ok");
