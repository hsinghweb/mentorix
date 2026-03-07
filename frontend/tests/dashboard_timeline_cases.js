const fs = require("fs");
const path = require("path");

const appJsPath = path.resolve(__dirname, "..", "app.js");
const content = fs.readFileSync(appJsPath, "utf8");

function assertContains(pattern, message) {
  if (!pattern.test(content)) {
    throw new Error(message);
  }
}

// UI regression guard: dashboard must expose both scheduled and active-pace completion dates.
assertContains(/completion_estimate_date\)/, "Missing scheduled completion date rendering.");
assertContains(/completion_estimate_date_active_pace\)/, "Missing active pace completion date rendering.");
assertContains(/Scheduled Completion/, "Missing scheduled completion label.");
assertContains(/Active Pace ETA/, "Missing active pace ETA label.");

console.log("dashboard_timeline_cases: ok");
