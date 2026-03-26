/**
 * Mentorix Frontend — ES Module Entry Point
 *
 * This file serves as the modular entry point that imports functionality
 * from the ES modules in `src/`. It re-exports all module APIs so they
 * can be loaded via `<script type="module">`.
 *
 * The original `app.js` monolith remains for backward compatibility.
 * This module demonstrates the target modular architecture.
 */

// ── Module imports ──────────────────────────────────────────────────
import * as auth from './src/auth.js';
import * as helpers from './src/helpers.js';
import * as dashboard from './src/dashboard.js';
import * as onboarding from './src/onboarding.js';
import * as testing from './src/testing.js';
import * as admin from './src/admin.js';

// ── Export unified API ──────────────────────────────────────────────
export { auth, helpers, dashboard, onboarding, testing, admin };

// ── Log module initialization ───────────────────────────────────────
console.info(
    '[Mentorix] ES modules loaded:',
    Object.keys({ auth, helpers, dashboard, onboarding, testing, admin }).join(', ')
);
