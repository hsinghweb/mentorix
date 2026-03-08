# Scope Guard Notes — Iteration 13

## 1.5 EduAgent Alignment Notes

### What We Adopt
- **Learner State Profile**: Interpretable signals (motivation, consistency, confusion-risk, pace, confidence) computed from existing journey data.
- **Memory Timeline**: Compact event log (wins/mistakes/weak_concepts/interventions) with bounded pruning.
- **Adaptive Interventions**: Rule-based recommendations with explicit reason codes and UI tooltips.

### What We Explicitly Exclude
- **AOI / Gaze / Motor Behavior**: EduAgent's research-only physiological tracking modules. These require eye-tracking hardware and are not applicable to Mentorix's web-based student journey.
- **Monolithic Script Architecture**: EduAgent uses single-script execution. Mentorix maintains its modular API-first service architecture.
- **Hardcoded Credentials / Simulation-Only Coupling**: No secret keys embedded in code, no simulation-only dependencies in student-facing flows.

---

## 2.7 DeepTutor Alignment Notes

### What We Adopt
- **Modularity Patterns**: Separation of concerns (config, prompt management, generation guards, telemetry).
- **Validation Gates**: Post-generation quality checks (format, deduplication, placeholder detection).
- **Telemetry**: Per-feature LLM cost/token tracking and circuit breaker visibility.

### What We Explicitly Exclude
- **Deep Research Module**: Notebook-style research workflows are outside Mentorix's student journey focus.
- **Co-Writer / General Notebook**: Broad writing-assistance features that don't serve the onboarding→plan→read→test→reminder→analytics flow.
- **Full Feature Parity**: We adopt architectural *patterns*, not DeepTutor's entire feature set.

### Student Journey Focus
Mentorix's core flow remains: **onboarding → plan → read → test → reminders → analytics**. Iteration 13 additions strengthen this flow without expanding into unrelated product surface.
