/* eslint-disable no-console */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

// normalizeMathDelimiters was extracted from app.js into renderer.js
const rendererPath = path.join(__dirname, "..", "renderer.js");
const source = fs.readFileSync(rendererPath, "utf8");
const match = source.match(/function normalizeMathDelimiters\(text\)\s*\{[\s\S]*?\n\}/);
if (!match) {
  throw new Error("normalizeMathDelimiters function not found in frontend/renderer.js");
}

const script = new vm.Script(`${match[0]}; normalizeMathDelimiters;`);
const fn = script.runInNewContext({});

const cases = [
  {
    name: "auto closes inline opener",
    input: "LCM is \\(\\frac{a}{b}",
    expect: "\\)",
  },
  {
    name: "auto closes display opener",
    input: "Rule: \\[a+b=c",
    expect: "\\]",
  },
  {
    name: "balances odd $$ delimiters",
    input: "$$x+y=z",
    expect: "$$",
  },
  {
    name: "keeps escaped delimiters normalized",
    input: "\\\\(x+y\\\\)",
    expect: "\\(x+y\\)",
  },
];

let failures = 0;
for (const tc of cases) {
  const out = fn(tc.input);
  if (!String(out).includes(tc.expect)) {
    failures += 1;
    console.error(`[FAIL] ${tc.name}\n  input:  ${tc.input}\n  output: ${out}\n  expect contains: ${tc.expect}`);
  } else {
    console.log(`[PASS] ${tc.name}`);
  }
}

if (failures > 0) {
  process.exit(1);
}

console.log("All math sanitization regression cases passed.");
