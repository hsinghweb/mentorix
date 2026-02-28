"""Class 10 Maths syllabus: chapters and subtopics (source: class-10-maths/syllabus/syllabus.txt)."""

from __future__ import annotations

SYLLABUS_CHAPTERS = [
    {"number": 1, "title": "Real Numbers", "subtopics": [
        {"id": "1.1", "title": "Introduction"},
        {"id": "1.2", "title": "The Fundamental Theorem of Arithmetic"},
        {"id": "1.3", "title": "Revisiting Irrational Numbers"},
        {"id": "1.4", "title": "Summary"},
    ]},
    {"number": 2, "title": "Polynomials", "subtopics": [
        {"id": "2.1", "title": "Introduction"},
        {"id": "2.2", "title": "Geometrical Meaning of the Zeroes of a Polynomial"},
        {"id": "2.3", "title": "Relationship between Zeroes and Coefficients of a Polynomial"},
        {"id": "2.4", "title": "Summary"},
    ]},
    {"number": 3, "title": "Pair of Linear Equations in Two Variables", "subtopics": [
        {"id": "3.1", "title": "Introduction"},
        {"id": "3.2", "title": "Graphical Method of Solution of a Pair of Linear Equations"},
        {"id": "3.3", "title": "Algebraic Methods of Solving a Pair of Linear Equations"},
        {"id": "3.3.1", "title": "Substitution Method"},
        {"id": "3.3.2", "title": "Elimination Method"},
        {"id": "3.4", "title": "Summary"},
    ]},
    {"number": 4, "title": "Quadratic Equations", "subtopics": [
        {"id": "4.1", "title": "Introduction"},
        {"id": "4.2", "title": "Quadratic Equations"},
        {"id": "4.3", "title": "Solution of a Quadratic Equation by Factorisation"},
        {"id": "4.4", "title": "Nature of Roots"},
        {"id": "4.5", "title": "Summary"},
    ]},
    {"number": 5, "title": "Arithmetic Progressions", "subtopics": [
        {"id": "5.1", "title": "Introduction"},
        {"id": "5.2", "title": "Arithmetic Progressions"},
        {"id": "5.3", "title": "nth Term of an AP"},
        {"id": "5.4", "title": "Sum of First n Terms of an AP"},
        {"id": "5.5", "title": "Summary"},
    ]},
    {"number": 6, "title": "Triangles", "subtopics": [
        {"id": "6.1", "title": "Introduction"},
        {"id": "6.2", "title": "Similar Figures"},
        {"id": "6.3", "title": "Similarity of Triangles"},
        {"id": "6.4", "title": "Criteria for Similarity of Triangles"},
        {"id": "6.5", "title": "Summary"},
    ]},
    {"number": 7, "title": "Coordinate Geometry", "subtopics": [
        {"id": "7.1", "title": "Introduction"},
        {"id": "7.2", "title": "Distance Formula"},
        {"id": "7.3", "title": "Section Formula"},
        {"id": "7.4", "title": "Summary"},
    ]},
    {"number": 8, "title": "Introduction to Trigonometry", "subtopics": [
        {"id": "8.1", "title": "Introduction"},
        {"id": "8.2", "title": "Trigonometric Ratios"},
        {"id": "8.3", "title": "Trigonometric Ratios of Some Specific Angles"},
        {"id": "8.4", "title": "Trigonometric Identities"},
        {"id": "8.5", "title": "Summary"},
    ]},
    {"number": 9, "title": "Some Applications of Trigonometry", "subtopics": [
        {"id": "9.1", "title": "Heights and Distances"},
        {"id": "9.2", "title": "Summary"},
    ]},
    {"number": 10, "title": "Circles", "subtopics": [
        {"id": "10.1", "title": "Introduction"},
        {"id": "10.2", "title": "Tangent to a Circle"},
        {"id": "10.3", "title": "Number of Tangents from a Point on a Circle"},
        {"id": "10.4", "title": "Summary"},
    ]},
    {"number": 11, "title": "Areas Related to Circles", "subtopics": [
        {"id": "11.1", "title": "Areas of Sector and Segment of a Circle"},
        {"id": "11.2", "title": "Summary"},
    ]},
    {"number": 12, "title": "Surface Areas and Volumes", "subtopics": [
        {"id": "12.1", "title": "Introduction"},
        {"id": "12.2", "title": "Surface Area of a Combination of Solids"},
        {"id": "12.3", "title": "Volume of a Combination of Solids"},
        {"id": "12.4", "title": "Summary"},
    ]},
    {"number": 13, "title": "Statistics", "subtopics": [
        {"id": "13.1", "title": "Introduction"},
        {"id": "13.2", "title": "Mean of Grouped Data"},
        {"id": "13.3", "title": "Mode of Grouped Data"},
        {"id": "13.4", "title": "Median of Grouped Data"},
        {"id": "13.5", "title": "Summary"},
    ]},
    {"number": 14, "title": "Probability", "subtopics": [
        {"id": "14.1", "title": "Probability — A Theoretical Approach"},
        {"id": "14.2", "title": "Summary"},
    ]},
]

def get_syllabus_for_api():
    """Return syllabus as list of chapters with subtopics for API response."""
    return SYLLABUS_CHAPTERS

def chapter_display_name(num: int) -> str:
    """Return 'Chapter N' used in plan/concept_mastery."""
    return f"Chapter {num}"
