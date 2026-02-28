#!/usr/bin/env python3
"""Verify Phase 0 invariants: syllabus 14 chapters, 5 diagnostic sets of 25 MCQs each."""
from __future__ import annotations

import sys


def main() -> int:
    from app.data.syllabus_structure import SYLLABUS_CHAPTERS, get_syllabus_for_api
    from app.data.diagnostic_question_sets import DIAGNOSTIC_SETS, get_random_diagnostic_set

    errors: list[str] = []

    # Syllabus: 14 chapters
    chapters = get_syllabus_for_api()
    if len(chapters) != 14:
        errors.append(f"SYLLABUS_CHAPTERS must have 14 chapters, got {len(chapters)}")
    for i, ch in enumerate(chapters, 1):
        if ch.get("number") != i:
            errors.append(f"Chapter at index {i-1} has number {ch.get('number')}, expected {i}")
        if not ch.get("subtopics"):
            errors.append(f"Chapter {i} ({ch.get('title')}) has no subtopics")

    # Diagnostic: 5 sets, 25 each, correct_index 0-3, 4 options
    if len(DIAGNOSTIC_SETS) != 5:
        errors.append(f"DIAGNOSTIC_SETS must have 5 sets, got {len(DIAGNOSTIC_SETS)}")
    for si, s in enumerate(DIAGNOSTIC_SETS):
        if len(s) != 25:
            errors.append(f"Set {si+1} must have 25 questions, got {len(s)}")
        for qi, q in enumerate(s):
            opts = q.get("options", [])
            if len(opts) != 4:
                errors.append(f"Set {si+1} q {qi+1}: expected 4 options, got {len(opts)}")
            ci = q.get("correct_index", -1)
            if not (0 <= ci <= 3):
                errors.append(f"Set {si+1} q {qi+1}: correct_index must be 0-3, got {ci}")
            cn = q.get("chapter_number", 0)
            if not (1 <= cn <= 14):
                errors.append(f"Set {si+1} q {qi+1}: chapter_number must be 1-14, got {cn}")

    # get_random_diagnostic_set returns 25 questions and answer_key
    questions, answer_key = get_random_diagnostic_set()
    if len(questions) != 25:
        errors.append(f"get_random_diagnostic_set() returned {len(questions)} questions, expected 25")
    if len(answer_key) != 25:
        errors.append(f"get_random_diagnostic_set() answer_key has {len(answer_key)} entries, expected 25")

    if errors:
        for e in errors:
            print("ERROR:", e)
        return 1
    print("Phase 0 verification OK: 14 chapters, 5 sets x 25 MCQs, get_random_diagnostic_set OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
