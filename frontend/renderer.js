/**
 * renderer.js — KaTeX / Markdown rendering pipeline.
 *
 * Extracted from app.js for maintainability.
 * Depends on: KaTeX auto-render, marked.js (loaded via CDN in index.html).
 * Must be loaded BEFORE app.js.
 */

/* global renderMathInElement, marked */

/**
 * Render KaTeX math expressions inside a DOM container.
 */
function renderKaTeX(container) {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(container, {
      delimiters: [
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true },
        { left: "$$", right: "$$", display: true },
      ],
      throwOnError: false,
    });
  }
}

/**
 * Normalize LaTeX math delimiters in raw text for consistent KaTeX rendering.
 * Fixes common LLM output issues: doubled backslashes, unmatched openers, etc.
 */
function normalizeMathDelimiters(text) {
  if (!text) return "";
  let s = String(text)
    .replace(/\\\\\\\(/g, "\\(")
    .replace(/\\\\\\\)/g, "\\)")
    .replace(/\\\\\\\[/g, "\\[")
    .replace(/\\\\\\\]/g, "\\]")
    // Heuristic fallback: wrap plain parenthesized LaTeX commands so KaTeX can render.
    .replace(/\(\s*(\\[A-Za-z]+[^()\n]{0,220})\s*\)/g, "\\($1\\)")
    .replace(/\r\n/g, "\n")
    .replace(/[\u200B-\u200D\uFEFF]/g, "");

  // Fix malformed inline closers: \(\sqrt{2} \\) -> \(\sqrt{2}\)
  s = s.replace(/\\\([\s\S]*?\\\\\)/g, (m) => {
    return m.replace(/\\\\$/, "").replace(/\\\\\)$/, "\\)");
  });
  s = s.replace(/\\\([\s\S]*?\\\\\)/g, "\\($1\\)");

  // Fix bare LaTeX fragments that end with closer but are not wrapped
  s = s.replace(
    /(^|[\s,;:([{\-])((?:\\[A-Za-z]+(?:\{[^{}]*\}|[A-Za-z0-9._^+-])*)+)\\\)/g,
    (m, p1, p2, offset, full) => {
      const at = Number(offset || 0) + String(p1 || "").length;
      if (at >= 2 && String(full).slice(at - 2, at) === "\\(") return m;
      return `${p1}\\(${p2.replace(/\\\)$/, "")}\\)`;
    }
  );

  // Fix orphan opener for single symbol: "\(p is ..." -> "\(p\) is ..."
  s = s.replace(
    /\\\(\s*([A-Za-z0-9][A-Za-z0-9_^{}]*)\s+([A-Za-z])/g,
    "\\($1\\) $2"
  );

  // Normalize accidental duplicated trailing slashes inside inline math
  s = s.replace(/\\\([^)]*?\\\\\s*\\\)/g, (m) => m.replace(/\\\\\s*\\\)$/, "\\)"));

  // Auto-close unmatched inline math openers "\("
  let inlineOpenBalance = 0;
  for (let i = 0; i < s.length - 1; i++) {
    if (s[i] === "\\" && s[i + 1] === "(") { inlineOpenBalance += 1; i += 1; continue; }
    if (s[i] === "\\" && s[i + 1] === ")") { if (inlineOpenBalance > 0) inlineOpenBalance -= 1; i += 1; }
  }
  if (inlineOpenBalance > 0) s += "\\)".repeat(inlineOpenBalance);

  // Auto-close unmatched display openers "\["
  let displayOpenBalance = 0;
  for (let i = 0; i < s.length - 1; i++) {
    if (s[i] === "\\" && s[i + 1] === "[") { displayOpenBalance += 1; i += 1; continue; }
    if (s[i] === "\\" && s[i + 1] === "]") { if (displayOpenBalance > 0) displayOpenBalance -= 1; i += 1; }
  }
  if (displayOpenBalance > 0) s += "\\]".repeat(displayOpenBalance);

  // Auto-close unbalanced $$ display delimiters
  const doubleDollarMatches = s.match(/\$\$/g);
  if (doubleDollarMatches && doubleDollarMatches.length % 2 !== 0) s += "$$";

  return s;
}

/**
 * Mask math blocks before markdown parsing so marked.js doesn't corrupt them.
 * Returns { masked, restore(html) }.
 */
function protectMathBlocks(text) {
  const source = normalizeMathDelimiters(text);
  const tokens = [];
  let idx = 0;
  const sanitizeMathToken = (token) => {
    let t = String(token || "");
    if (t.startsWith("\\(") && t.endsWith("\\)")) {
      let inner = t.slice(2, -2).trim();
      inner = inner.replace(/\\\\\s*$/, "").trim();
      return `\\(${inner}\\)`;
    }
    if (t.startsWith("\\[") && t.endsWith("\\]")) {
      let inner = t.slice(2, -2).trim();
      inner = inner.replace(/\\\\\s*$/, "").trim();
      return `\\[${inner}\\]`;
    }
    return t;
  };
  const put = (m) => {
    const key = `@@MATH_BLOCK_${idx++}@@`;
    tokens.push([key, sanitizeMathToken(m)]);
    return key;
  };
  const masked = source
    .replace(/\\\([\s\S]*?\\\)/g, put)
    .replace(/\\\[[\s\S]*?\\\]/g, put)
    .replace(/\$\$[\s\S]*?\$\$/g, put)
    .replace(/\$[^$\n]+\$/g, put);
  return {
    masked,
    restore: (html) => {
      let out = String(html || "");
      for (const [key, value] of tokens) out = out.split(key).join(value);
      return out;
    },
  };
}

/**
 * Convert markdown text to HTML, preserving math blocks.
 */
function mdToHtml(md) {
  const { masked, restore } = protectMathBlocks(md);
  if (!masked) return "";
  if (typeof marked !== "undefined" && typeof marked.parse === "function") {
    try {
      return restore(marked.parse(masked, { breaks: true, gfm: true }));
    } catch (err) {
      console.warn("Markdown parse failed, using safe fallback:", err);
    }
  }
  return `<pre style="white-space:pre-wrap;color:var(--text-primary)">${restore(masked
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>"))}</pre>`;
}

/**
 * Convert inline markdown to HTML (no block elements).
 */
function mdInlineToHtml(md) {
  const { masked, restore } = protectMathBlocks(md);
  if (!masked) return "";
  if (typeof marked !== "undefined" && typeof marked.parseInline === "function") {
    return restore(marked.parseInline(masked));
  }
  return restore(masked
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;"));
}
