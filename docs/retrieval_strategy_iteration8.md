# Retrieval Strategy (Iteration 8)

## Goal
Use deterministic subsection fetch for primary learning content, and use vector retrieval only where semantic lookup adds value.

## Path A: Subsection Read/Test Generation (Primary)
- Source-of-truth key: `chapter_number + section_id`
- Retrieval order:
1. Mongo `canonical_sections` lookup (exact key match)
2. If missing, exact DB query on `embedding_chunks` filtered by `chapter_number` and `section_id`
3. Persist assembled canonical text back to Mongo `canonical_sections`
- LLM input: canonical subsection source + learner profile/tone config
- Result caching: Mongo `generated_content` and `generated_tests` keyed by learner/chapter/section

## Path B: Final Chapter Test
- Source-of-truth key: `learner_id + chapter_number + __chapter__`
- Retrieval:
1. Mongo `generated_tests` exact cache key
2. If miss/regenerate, generate from chapter context and persist under `__chapter__`

## Path C: Explain-Per-Question
- Source-of-truth key: `learner_id + test_id + question_id`
- Retrieval:
1. Mongo `question_explanations` cache
2. If miss/regenerate, gather question context and section canonical source
3. Optional chapter fallback chunks if section source unavailable
- Output: grounded explanation + remediation tip

## Where Similarity/Vector Retrieval Is Used
- Not used as primary fetch for subsection read/test generation.
- Used as fallback context source when canonical section text is unavailable.
- Can be expanded for explain mode when broader semantic support is needed.
