#!/usr/bin/env python3
"""
Validate a course directory and print env vars + ingestion command for onboarding a new course.
Usage (from repo root): python API/scripts/onboard_course.py <course-dir> [chapter-count]
Example: python API/scripts/onboard_course.py class-10-science 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate course dir and print onboarding steps")
    parser.add_argument("course_dir", help="Course directory name under repo root (e.g. class-10-science)")
    parser.add_argument(
        "chapter_count",
        nargs="?",
        type=int,
        default=3,
        help="Max chapter PDFs to ingest (default 3)",
    )
    args = parser.parse_args()

    root = _repo_root()
    course_path = root / args.course_dir
    if not course_path.is_dir():
        print(f"Error: Course directory not found: {course_path}", file=sys.stderr)
        return 1

    syllabus_dir = course_path / "syllabus"
    syllabus_txt = syllabus_dir / "syllabus.txt"
    syllabus_pdf = syllabus_dir / "syllabus.pdf"
    if not syllabus_txt.exists() and not syllabus_pdf.exists():
        print(f"Error: Missing syllabus. Add {course_path}/syllabus/syllabus.txt or syllabus.pdf", file=sys.stderr)
        return 1

    chapters_dir = course_path / "chapters"
    if not chapters_dir.is_dir():
        print(f"Error: Missing chapters directory: {chapters_dir}", file=sys.stderr)
        return 1

    chapter_files = sorted(chapters_dir.glob("ch_*.pdf")) or sorted(chapters_dir.glob("ch-*.pdf"))
    if not chapter_files:
        print(f"Warning: No ch_*.pdf or ch-*.pdf found in {chapters_dir}", file=sys.stderr)
    else:
        print(f"Found {len(chapter_files)} chapter PDF(s): {[f.name for f in chapter_files[:10]]}{'...' if len(chapter_files) > 10 else ''}")

    print()
    print("# Set these environment variables, then run ingestion (e.g. POST /grounding/ingest):")
    print()
    print(f"export GROUNDING_DATA_DIR={args.course_dir}")
    print("export GROUNDING_SYLLABUS_RELATIVE_PATH=syllabus/syllabus.pdf")
    print("export GROUNDING_CHAPTERS_DIR=chapters")
    print(f"export GROUNDING_CHAPTER_COUNT={args.chapter_count}")
    print()
    print("# Then run ingestion:")
    print('curl -X POST "http://localhost:8000/grounding/ingest?force_rebuild=false"')
    print()
    print("# Verify: GET http://localhost:8000/grounding/status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
