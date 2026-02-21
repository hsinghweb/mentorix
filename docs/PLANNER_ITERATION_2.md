# Mentorix Iteration 2 Planner

Status date: 2026-02-21  
Goal: close remaining spec-alignment gaps after MVP completion.

---

## 1) Spec Gaps Carryover

### From Iteration 1
- [x] Formal pluggable LLM provider abstraction (Gemini/OpenAI/Groq/Claude-ready interface)
- [x] Token usage logging contract (prompt/completion/total estimates)
- [x] Deeper vector memory coverage for generated artifacts/misconceptions
- [x] Optional FAISS/Chroma adapter path (keep pgvector as default)
- [x] Future-extension hook interfaces (BKT/RL/multimodal/XAI)

---

## 2) Iteration 2 Scope

### Immediate
- [x] Add LLM provider interface and migrate content agent to use it
- [x] Add usage metrics logging from content generation path
- [x] Add generated-explanation vector persistence table + write path
- [x] Add extension hook interface placeholders

### Secondary
- [x] Add retrieval toggle for generated artifacts (feature flag)
- [x] Add optional vector backend adapter abstraction (pgvector/faiss/chroma)

---

## 3) Exit Criteria

- [x] Content generation works with provider abstraction in place
- [x] Structured logs include token usage fields
- [x] Generated explanations are persisted with embeddings
- [x] Existing smoke/integration tests still pass
