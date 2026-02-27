"""
Predefined diagnostic question sets for Class 10 Mathematics onboarding.
Each set has exactly 25 MCQs with 4 options (A, B, C, D); one correct per question.
Math is expressed with \\( \\) for inline LaTeX so the frontend can render with KaTeX.
Answer keys are stored and used to score the student and build the global profile.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.onboarding import DiagnosticQuestion

# Each item: question_id, prompt, options [A,B,C,D], correct_index (0=A, 1=B, 2=C, 3=D), chapter_number (1-14)
SET_1 = [
    {
        "question_id": "q_1",
        "prompt": "The decimal expansion of \\( \\frac{13}{40} \\) is",
        "options": ["Terminating", "Non-terminating recurring", "Non-terminating non-recurring", "Irrational"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_2",
        "prompt": "The value of \\( \\sqrt{75} \\) in simplest radical form is",
        "options": ["\\( 5\\sqrt{3} \\)", "\\( 3\\sqrt{5} \\)", "\\( 15\\sqrt{5} \\)", "\\( 25\\sqrt{3} \\)"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_3",
        "prompt": "If \\( p(x)=x^2-4x+3 \\), then \\( p(1) \\) equals",
        "options": ["0", "1", "2", "3"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_4",
        "prompt": "The point (−4, 0) lies on",
        "options": ["x-axis", "y-axis", "origin", "second quadrant"],
        "correct_index": 0,
        "chapter_number": 7,
    },
    {
        "question_id": "q_5",
        "prompt": "The graph of equation \\( y=2x+1 \\) is a",
        "options": ["circle", "straight line", "parabola", "point"],
        "correct_index": 1,
        "chapter_number": 3,
    },
    {
        "question_id": "q_6",
        "prompt": "According to Euclid, a straight line can be drawn joining",
        "options": ["any two points", "only parallel points", "only intersecting points", "one point only"],
        "correct_index": 0,
        "chapter_number": 5,
    },
    {
        "question_id": "q_7",
        "prompt": "If two parallel lines are cut by a transversal, corresponding angles are",
        "options": ["supplementary", "equal", "complementary", "unequal"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_8",
        "prompt": "In a triangle, the angle opposite the longest side is",
        "options": ["smallest", "equal", "largest", "right angle"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_9",
        "prompt": "If one angle of a parallelogram is 70°, the adjacent angle is",
        "options": ["70°", "90°", "110°", "140°"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_10",
        "prompt": "Equal chords of a circle are",
        "options": ["unequal in distance from centre", "equidistant from centre", "parallel", "tangents"],
        "correct_index": 1,
        "chapter_number": 10,
    },
    {
        "question_id": "q_11",
        "prompt": "Using Heron's formula, area of triangle with sides 5, 5, 6 is",
        "options": ["12", "24", "36", "48"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_12",
        "prompt": "Curved surface area of cylinder of radius 7 cm and height 10 cm is",
        "options": ["\\( 140\\pi \\)", "\\( 70\\pi \\)", "\\( 98\\pi \\)", "\\( 490\\pi \\)"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_13",
        "prompt": "Mean of 5, 7, 9, 11 is",
        "options": ["7", "8", "9", "10"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_14",
        "prompt": "Probability of getting a number less than 3 when throwing a die is",
        "options": ["1/6", "1/3", "1/2", "2/3"],
        "correct_index": 1,
        "chapter_number": 14,
    },
    {
        "question_id": "q_15",
        "prompt": "Which of the following is irrational?",
        "options": ["0.25", "\\( \\sqrt{7} \\)", "3/5", "−2"],
        "correct_index": 1,
        "chapter_number": 1,
    },
    {
        "question_id": "q_16",
        "prompt": "The zero of polynomial \\( 2x-6 \\) is",
        "options": ["2", "3", "−3", "6"],
        "correct_index": 1,
        "chapter_number": 2,
    },
    {
        "question_id": "q_17",
        "prompt": "Distance of point (0, 5) from origin is",
        "options": ["0", "5", "√5", "25"],
        "correct_index": 1,
        "chapter_number": 7,
    },
    {
        "question_id": "q_18",
        "prompt": "If a transversal cuts two parallel lines, interior angles on same side are",
        "options": ["equal", "supplementary", "complementary", "acute"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_19",
        "prompt": "If two sides of a triangle are 3 and 4 and included angle is 90°, the third side is",
        "options": ["5", "6", "7", "8"],
        "correct_index": 0,
        "chapter_number": 6,
    },
    {
        "question_id": "q_20",
        "prompt": "A quadrilateral with exactly one pair of parallel sides is",
        "options": ["parallelogram", "trapezium", "rectangle", "rhombus"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_21",
        "prompt": "The angle subtended at centre is twice the angle subtended at",
        "options": ["diameter", "tangent", "circumference", "chord"],
        "correct_index": 2,
        "chapter_number": 10,
    },
    {
        "question_id": "q_22",
        "prompt": "Semi-perimeter of triangle with sides 6, 8, 10 is",
        "options": ["12", "10", "24", "14"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_23",
        "prompt": "Volume of cylinder of radius 3 cm and height 7 cm is",
        "options": ["\\( 21\\pi \\)", "\\( 63\\pi \\)", "\\( 189\\pi \\)", "\\( 441\\pi \\)"],
        "correct_index": 2,
        "chapter_number": 12,
    },
    {
        "question_id": "q_24",
        "prompt": "Median of data 2, 3, 5, 8, 10 is",
        "options": ["3", "5", "8", "10"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_25",
        "prompt": "Probability of sure event is",
        "options": ["0", "1/2", "1", "2"],
        "correct_index": 2,
        "chapter_number": 14,
    },
]

# Set 2 — 25 MCQs with answer key (1-B, 2-A, 3-A, 4-D, 5-B, 6-C, 7-A, 8-B, 9-C, 10-B, 11-A, 12-D, 13-B, 14-C, 15-C, 16-A, 17-B, 18-B, 19-A, 20-B, 21-C, 22-A, 23-D, 24-B, 25-A)
SET_2 = [
    {
        "question_id": "q_1",
        "prompt": "The decimal expansion of \\( \\frac{7}{12} \\) is",
        "options": ["Terminating", "Non-terminating recurring", "Non-terminating non-recurring", "Irrational"],
        "correct_index": 1,
        "chapter_number": 1,
    },
    {
        "question_id": "q_2",
        "prompt": "The simplified form of \\( \\sqrt{98} \\) is",
        "options": ["\\( 7\\sqrt{2} \\)", "\\( 14\\sqrt{2} \\)", "\\( 49\\sqrt{2} \\)", "\\( 2\\sqrt{7} \\)"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_3",
        "prompt": "If \\( p(x)=x^2-9 \\), then \\( p(3) \\) equals",
        "options": ["0", "3", "6", "9"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_4",
        "prompt": "The point (2, −5) lies in",
        "options": ["first quadrant", "second quadrant", "third quadrant", "fourth quadrant"],
        "correct_index": 3,
        "chapter_number": 7,
    },
    {
        "question_id": "q_5",
        "prompt": "Equation \\( x=4 \\) represents",
        "options": ["horizontal line", "vertical line", "circle", "point"],
        "correct_index": 1,
        "chapter_number": 3,
    },
    {
        "question_id": "q_6",
        "prompt": "Euclid defined a point as",
        "options": ["having length", "having breadth", "having position but no dimension", "having area"],
        "correct_index": 2,
        "chapter_number": 5,
    },
    {
        "question_id": "q_7",
        "prompt": "If two parallel lines are cut by a transversal, alternate interior angles are",
        "options": ["equal", "supplementary", "complementary", "unequal"],
        "correct_index": 0,
        "chapter_number": 6,
    },
    {
        "question_id": "q_8",
        "prompt": "The sum of angles of a triangle is",
        "options": ["90°", "180°", "270°", "360°"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_9",
        "prompt": "Diagonals of a rectangle are",
        "options": ["unequal", "perpendicular", "equal", "parallel"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_10",
        "prompt": "The line joining centre to midpoint of chord is",
        "options": ["parallel to chord", "perpendicular to chord", "tangent", "diameter"],
        "correct_index": 1,
        "chapter_number": 10,
    },
    {
        "question_id": "q_11",
        "prompt": "Area of triangle with sides 3, 4, 5 using Heron's formula is",
        "options": ["6", "12", "24", "48"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_12",
        "prompt": "Total surface area of cube of side 4 cm is",
        "options": ["16", "32", "64", "96"],
        "correct_index": 3,
        "chapter_number": 12,
    },
    {
        "question_id": "q_13",
        "prompt": "Mean of 3, 6, 9, 12 is",
        "options": ["6", "7.5", "8", "9"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_14",
        "prompt": "Probability of getting even number on a die is",
        "options": ["1/6", "1/3", "1/2", "2/3"],
        "correct_index": 2,
        "chapter_number": 14,
    },
    {
        "question_id": "q_15",
        "prompt": "Which of the following is rational?",
        "options": ["\\( \\sqrt{3} \\)", "π", "0.125", "\\( \\sqrt{5} \\)"],
        "correct_index": 2,
        "chapter_number": 1,
    },
    {
        "question_id": "q_16",
        "prompt": "The zero of polynomial \\( 3x+6 \\) is",
        "options": ["−2", "2", "3", "−3"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_17",
        "prompt": "Distance of point (−6, 0) from origin is",
        "options": ["0", "6", "√6", "36"],
        "correct_index": 1,
        "chapter_number": 7,
    },
    {
        "question_id": "q_18",
        "prompt": "Interior angles on same side of transversal are",
        "options": ["equal", "supplementary", "complementary", "acute"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_19",
        "prompt": "If two sides of triangle are 5 and 12 with right angle between them, third side is",
        "options": ["13", "14", "15", "17"],
        "correct_index": 0,
        "chapter_number": 6,
    },
    {
        "question_id": "q_20",
        "prompt": "A parallelogram with right angle is",
        "options": ["rhombus", "rectangle", "trapezium", "kite"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_21",
        "prompt": "Angle in semicircle is",
        "options": ["acute", "obtuse", "right angle", "straight angle"],
        "correct_index": 2,
        "chapter_number": 10,
    },
    {
        "question_id": "q_22",
        "prompt": "Semi-perimeter of triangle with sides 5, 12, 13 is",
        "options": ["15", "30", "20", "10"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_23",
        "prompt": "Volume of cube of side 5 cm is",
        "options": ["25", "75", "100", "125"],
        "correct_index": 3,
        "chapter_number": 12,
    },
    {
        "question_id": "q_24",
        "prompt": "Mode of data 2, 3, 3, 5, 7 is",
        "options": ["2", "3", "5", "7"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_25",
        "prompt": "Probability of impossible event is",
        "options": ["0", "1/2", "1", "2"],
        "correct_index": 0,
        "chapter_number": 14,
    },
]

# Set 3 — 25 MCQs (answer key: 1-A, 2-A, 3-A, 4-B, 5-B, 6-B, 7-B, 8-C, 9-B, 10-C, 11-A, 12-B, 13-B, 14-B, 15-C, 16-A, 17-B, 18-C, 19-A, 20-C, 21-C, 22-A, 23-C, 24-B, 25-B)
SET_3 = [
    {
        "question_id": "q_1",
        "prompt": "The decimal expansion of \\( \\frac{11}{25} \\) is",
        "options": ["Terminating", "Non-terminating recurring", "Non-terminating non-recurring", "Irrational"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_2",
        "prompt": "The simplest form of \\( \\sqrt{72} \\) is",
        "options": ["\\( 6\\sqrt{2} \\)", "\\( 3\\sqrt{8} \\)", "\\( 12\\sqrt{2} \\)", "\\( 8\\sqrt{3} \\)"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_3",
        "prompt": "If \\( p(x)=x^2-5x+6 \\), then \\( p(2) \\) equals",
        "options": ["0", "1", "2", "3"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_4",
        "prompt": "The point (−3, 4) lies in",
        "options": ["first quadrant", "second quadrant", "third quadrant", "fourth quadrant"],
        "correct_index": 1,
        "chapter_number": 7,
    },
    {
        "question_id": "q_5",
        "prompt": "Equation \\( y=-3 \\) represents",
        "options": ["vertical line", "horizontal line", "circle", "point"],
        "correct_index": 1,
        "chapter_number": 3,
    },
    {
        "question_id": "q_6",
        "prompt": "According to Euclid, a line has",
        "options": ["breadth only", "length without breadth", "area", "volume"],
        "correct_index": 1,
        "chapter_number": 5,
    },
    {
        "question_id": "q_7",
        "prompt": "If two lines intersect, vertically opposite angles are",
        "options": ["supplementary", "equal", "complementary", "unequal"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_8",
        "prompt": "If sides of triangle are 7, 7, 7, the triangle is",
        "options": ["scalene", "isosceles", "equilateral", "right-angled"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_9",
        "prompt": "Opposite sides of parallelogram are",
        "options": ["unequal", "parallel and equal", "perpendicular", "intersecting"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_10",
        "prompt": "The longest chord of a circle is",
        "options": ["radius", "tangent", "diameter", "arc"],
        "correct_index": 2,
        "chapter_number": 10,
    },
    {
        "question_id": "q_11",
        "prompt": "Area of triangle with sides 6, 8, 10 using Heron's formula is",
        "options": ["24", "48", "12", "36"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_12",
        "prompt": "Curved surface area of cylinder with radius 5 cm and height 12 cm is",
        "options": ["\\( 60\\pi \\)", "\\( 120\\pi \\)", "\\( 240\\pi \\)", "\\( 300\\pi \\)"],
        "correct_index": 1,
        "chapter_number": 12,
    },
    {
        "question_id": "q_13",
        "prompt": "Mean of 4, 8, 12, 16 is",
        "options": ["8", "10", "12", "14"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_14",
        "prompt": "Probability of getting number greater than 4 on a die is",
        "options": ["1/6", "1/3", "1/2", "2/3"],
        "correct_index": 1,
        "chapter_number": 14,
    },
    {
        "question_id": "q_15",
        "prompt": "Which of the following is irrational?",
        "options": ["0.75", "2/3", "\\( \\sqrt{11} \\)", "−1"],
        "correct_index": 2,
        "chapter_number": 1,
    },
    {
        "question_id": "q_16",
        "prompt": "The zero of polynomial \\( x+8 \\) is",
        "options": ["−8", "8", "0", "1"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_17",
        "prompt": "Distance of point (0, −9) from origin is",
        "options": ["0", "9", "√9", "81"],
        "correct_index": 1,
        "chapter_number": 7,
    },
    {
        "question_id": "q_18",
        "prompt": "If a transversal cuts parallel lines, corresponding angles are",
        "options": ["unequal", "supplementary", "equal", "complementary"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_19",
        "prompt": "If two sides of triangle are 8 and 15 with right angle between them, third side is",
        "options": ["17", "18", "19", "20"],
        "correct_index": 0,
        "chapter_number": 6,
    },
    {
        "question_id": "q_20",
        "prompt": "A parallelogram with all sides equal and right angles is",
        "options": ["rectangle", "rhombus", "square", "trapezium"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_21",
        "prompt": "Angle subtended by diameter at circumference is",
        "options": ["acute", "obtuse", "right angle", "straight angle"],
        "correct_index": 2,
        "chapter_number": 10,
    },
    {
        "question_id": "q_22",
        "prompt": "Semi-perimeter of triangle with sides 7, 24, 25 is",
        "options": ["28", "56", "24", "30"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_23",
        "prompt": "Volume of cylinder with radius 2 cm and height 7 cm is",
        "options": ["\\( 14\\pi \\)", "\\( 28\\pi \\)", "\\( 56\\pi \\)", "\\( 84\\pi \\)"],
        "correct_index": 2,
        "chapter_number": 12,
    },
    {
        "question_id": "q_24",
        "prompt": "Median of data 1, 3, 5, 7, 9 is",
        "options": ["3", "5", "7", "9"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_25",
        "prompt": "Probability of getting tail in one toss of coin is",
        "options": ["0", "1/2", "1", "2"],
        "correct_index": 1,
        "chapter_number": 14,
    },
]

# Set 4 — 25 MCQs (answer key: 1-A, 2-A, 3-A, 4-D, 5-A, 6-C, 7-B, 8-C, 9-B, 10-C, 11-A, 12-B, 13-B, 14-B, 15-C, 16-A, 17-B, 18-B, 19-A, 20-C, 21-C, 22-A, 23-D, 24-A, 25-C)
SET_4 = [
    {
        "question_id": "q_1",
        "prompt": "The decimal expansion of \\( \\frac{9}{16} \\) is",
        "options": ["Terminating", "Non-terminating recurring", "Non-terminating non-recurring", "Irrational"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_2",
        "prompt": "The simplest form of \\( \\sqrt{108} \\) is",
        "options": ["\\( 6\\sqrt{3} \\)", "\\( 3\\sqrt{12} \\)", "\\( 12\\sqrt{3} \\)", "\\( 9\\sqrt{3} \\)"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_3",
        "prompt": "If \\( p(x)=x^2-7x+10 \\), then \\( p(5) \\) equals",
        "options": ["0", "2", "3", "5"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_4",
        "prompt": "The point (4, −2) lies in",
        "options": ["first quadrant", "second quadrant", "third quadrant", "fourth quadrant"],
        "correct_index": 3,
        "chapter_number": 7,
    },
    {
        "question_id": "q_5",
        "prompt": "Equation \\( y=0 \\) represents",
        "options": ["x-axis", "y-axis", "circle", "vertical line"],
        "correct_index": 0,
        "chapter_number": 3,
    },
    {
        "question_id": "q_6",
        "prompt": "Euclid's axiom states that things equal to the same thing are",
        "options": ["unequal", "parallel", "equal", "perpendicular"],
        "correct_index": 2,
        "chapter_number": 5,
    },
    {
        "question_id": "q_7",
        "prompt": "If two parallel lines are cut by a transversal, alternate exterior angles are",
        "options": ["supplementary", "equal", "complementary", "unequal"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_8",
        "prompt": "If sides of triangle are 5, 6, 7, the triangle is",
        "options": ["equilateral", "isosceles", "scalene", "right-angled"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_9",
        "prompt": "Diagonals of a rhombus are",
        "options": ["equal", "perpendicular", "parallel", "unequal"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_10",
        "prompt": "A tangent to a circle is perpendicular to radius at",
        "options": ["centre", "midpoint", "point of contact", "diameter"],
        "correct_index": 2,
        "chapter_number": 10,
    },
    {
        "question_id": "q_11",
        "prompt": "Area of triangle with sides 7, 8, 9 using Heron's formula is",
        "options": ["\\( \\sqrt{720} \\)", "24", "36", "48"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_12",
        "prompt": "Total surface area of cylinder with radius 3 cm and height 5 cm is",
        "options": ["\\( 30\\pi \\)", "\\( 48\\pi \\)", "\\( 60\\pi \\)", "\\( 90\\pi \\)"],
        "correct_index": 1,
        "chapter_number": 12,
    },
    {
        "question_id": "q_13",
        "prompt": "Mean of 2, 6, 10, 14 is",
        "options": ["6", "8", "10", "12"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_14",
        "prompt": "Probability of getting a multiple of 3 on a die is",
        "options": ["1/6", "1/3", "1/2", "2/3"],
        "correct_index": 1,
        "chapter_number": 14,
    },
    {
        "question_id": "q_15",
        "prompt": "Which of the following is rational?",
        "options": ["\\( \\sqrt{13} \\)", "π", "0.375", "\\( \\sqrt{2} \\)"],
        "correct_index": 2,
        "chapter_number": 1,
    },
    {
        "question_id": "q_16",
        "prompt": "The zero of polynomial \\( 4x-8 \\) is",
        "options": ["2", "−2", "4", "−4"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_17",
        "prompt": "Distance of point (−5, 0) from origin is",
        "options": ["0", "5", "√5", "25"],
        "correct_index": 1,
        "chapter_number": 7,
    },
    {
        "question_id": "q_18",
        "prompt": "Interior angles on same side of transversal between parallel lines are",
        "options": ["equal", "supplementary", "complementary", "acute"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_19",
        "prompt": "If two sides of triangle are 9 and 12 with right angle between them, third side is",
        "options": ["15", "16", "17", "18"],
        "correct_index": 0,
        "chapter_number": 6,
    },
    {
        "question_id": "q_20",
        "prompt": "A parallelogram with diagonals equal and perpendicular is",
        "options": ["rectangle", "rhombus", "square", "trapezium"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_21",
        "prompt": "Angle subtended by arc at centre is always",
        "options": ["equal to angle at circumference", "half of angle at circumference", "twice angle at circumference", "zero"],
        "correct_index": 2,
        "chapter_number": 10,
    },
    {
        "question_id": "q_22",
        "prompt": "Semi-perimeter of triangle with sides 8, 15, 17 is",
        "options": ["20", "40", "30", "25"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_23",
        "prompt": "Volume of cube of side 6 cm is",
        "options": ["36", "72", "108", "216"],
        "correct_index": 3,
        "chapter_number": 12,
    },
    {
        "question_id": "q_24",
        "prompt": "Mode of data 4, 4, 5, 6, 7 is",
        "options": ["4", "5", "6", "7"],
        "correct_index": 0,
        "chapter_number": 13,
    },
    {
        "question_id": "q_25",
        "prompt": "Probability of sure event is",
        "options": ["0", "1/2", "1", "2"],
        "correct_index": 2,
        "chapter_number": 14,
    },
]

# Set 5 — 25 MCQs (answer key: 1-A, 2-A, 3-A, 4-C, 5-B, 6-A, 7-C, 8-D, 9-B, 10-A, 11-A, 12-B, 13-B, 14-C, 15-C, 16-A, 17-B, 18-B, 19-C, 20-B, 21-B, 22-A, 23-C, 24-B, 25-A)
SET_5 = [
    {
        "question_id": "q_1",
        "prompt": "The decimal expansion of \\( \\frac{3}{20} \\) is",
        "options": ["Terminating", "Non-terminating recurring", "Non-terminating non-recurring", "Irrational"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_2",
        "prompt": "The simplest form of \\( \\sqrt{200} \\) is",
        "options": ["\\( 10\\sqrt{2} \\)", "\\( 5\\sqrt{8} \\)", "\\( 20\\sqrt{2} \\)", "\\( 8\\sqrt{5} \\)"],
        "correct_index": 0,
        "chapter_number": 1,
    },
    {
        "question_id": "q_3",
        "prompt": "If \\( p(x)=x^2-6x+8 \\), then \\( p(2) \\) equals",
        "options": ["0", "2", "4", "6"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_4",
        "prompt": "The point (−2, −3) lies in",
        "options": ["first quadrant", "second quadrant", "third quadrant", "fourth quadrant"],
        "correct_index": 2,
        "chapter_number": 7,
    },
    {
        "question_id": "q_5",
        "prompt": "Equation \\( x=0 \\) represents",
        "options": ["x-axis", "y-axis", "horizontal line", "circle"],
        "correct_index": 1,
        "chapter_number": 3,
    },
    {
        "question_id": "q_6",
        "prompt": "According to Euclid, a line segment can be produced",
        "options": ["indefinitely", "finitely", "only once", "perpendicular"],
        "correct_index": 0,
        "chapter_number": 5,
    },
    {
        "question_id": "q_7",
        "prompt": "If a transversal cuts parallel lines, corresponding angles are",
        "options": ["supplementary", "complementary", "equal", "unequal"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_8",
        "prompt": "In a triangle, if one angle is 90°, the triangle is",
        "options": ["scalene", "isosceles", "equilateral", "right-angled"],
        "correct_index": 3,
        "chapter_number": 6,
    },
    {
        "question_id": "q_9",
        "prompt": "Opposite angles of parallelogram are",
        "options": ["unequal", "equal", "complementary", "right angles"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_10",
        "prompt": "The perpendicular from centre to chord",
        "options": ["bisects chord", "equals chord", "tangent", "diameter"],
        "correct_index": 0,
        "chapter_number": 10,
    },
    {
        "question_id": "q_11",
        "prompt": "Area of triangle with sides 4, 13, 15 using Heron's formula is",
        "options": ["24", "30", "36", "48"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_12",
        "prompt": "Curved surface area of cylinder with radius 4 cm and height 10 cm is",
        "options": ["\\( 40\\pi \\)", "\\( 80\\pi \\)", "\\( 160\\pi \\)", "\\( 200\\pi \\)"],
        "correct_index": 1,
        "chapter_number": 12,
    },
    {
        "question_id": "q_13",
        "prompt": "Mean of 1, 5, 9, 13 is",
        "options": ["6", "7", "8", "9"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_14",
        "prompt": "Probability of getting odd number on a die is",
        "options": ["1/6", "1/3", "1/2", "2/3"],
        "correct_index": 2,
        "chapter_number": 14,
    },
    {
        "question_id": "q_15",
        "prompt": "Which of the following is irrational?",
        "options": ["0.2", "3/7", "\\( \\sqrt{19} \\)", "−4"],
        "correct_index": 2,
        "chapter_number": 1,
    },
    {
        "question_id": "q_16",
        "prompt": "The zero of polynomial \\( 5x+10 \\) is",
        "options": ["−2", "2", "5", "−5"],
        "correct_index": 0,
        "chapter_number": 2,
    },
    {
        "question_id": "q_17",
        "prompt": "Distance of point (7, 0) from origin is",
        "options": ["0", "7", "√7", "49"],
        "correct_index": 1,
        "chapter_number": 7,
    },
    {
        "question_id": "q_18",
        "prompt": "Interior angles on same side of transversal are",
        "options": ["equal", "supplementary", "complementary", "acute"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_19",
        "prompt": "If two sides of triangle are 12 and 16 with right angle between them, third side is",
        "options": ["18", "19", "20", "21"],
        "correct_index": 2,
        "chapter_number": 6,
    },
    {
        "question_id": "q_20",
        "prompt": "A parallelogram with equal diagonals is",
        "options": ["rhombus", "rectangle", "trapezium", "kite"],
        "correct_index": 1,
        "chapter_number": 6,
    },
    {
        "question_id": "q_21",
        "prompt": "Angle subtended by chord at centre is always",
        "options": ["half of angle at circumference", "twice angle at circumference", "equal to angle at circumference", "zero"],
        "correct_index": 1,
        "chapter_number": 10,
    },
    {
        "question_id": "q_22",
        "prompt": "Semi-perimeter of triangle with sides 9, 40, 41 is",
        "options": ["45", "90", "50", "40"],
        "correct_index": 0,
        "chapter_number": 12,
    },
    {
        "question_id": "q_23",
        "prompt": "Volume of cylinder with radius 3 cm and height 10 cm is",
        "options": ["\\( 30\\pi \\)", "\\( 60\\pi \\)", "\\( 90\\pi \\)", "\\( 270\\pi \\)"],
        "correct_index": 2,
        "chapter_number": 12,
    },
    {
        "question_id": "q_24",
        "prompt": "Median of data 3, 5, 7, 9, 11 is",
        "options": ["5", "7", "9", "11"],
        "correct_index": 1,
        "chapter_number": 13,
    },
    {
        "question_id": "q_25",
        "prompt": "Probability of impossible event is",
        "options": ["0", "1/2", "1", "2"],
        "correct_index": 0,
        "chapter_number": 14,
    },
]

# All five predefined diagnostic sets
DIAGNOSTIC_SETS = [SET_1, SET_2, SET_3, SET_4, SET_5]


def get_random_diagnostic_set() -> tuple[list["DiagnosticQuestion"], dict[str, str]]:
    """
    Pick one of the predefined diagnostic sets at random and return
    (questions, answer_key). answer_key maps question_id -> correct option text (lowercased)
    for scoring the student's submitted answers.
    """
    from app.schemas.onboarding import DiagnosticQuestion

    if not DIAGNOSTIC_SETS:
        return [], {}

    raw_set = random.choice(DIAGNOSTIC_SETS)
    questions: list[DiagnosticQuestion] = []
    answer_key: dict[str, str] = {}

    for item in raw_set:
        qid = item["question_id"]
        options = list(item["options"])
        correct_index = int(item["correct_index"])
        if correct_index < 0 or correct_index >= len(options):
            correct_index = 0
        chapter_number = int(item.get("chapter_number", 1))
        if chapter_number < 1 or chapter_number > 14:
            chapter_number = 1

        questions.append(
            DiagnosticQuestion(
                question_id=qid,
                question_type="mcq",
                chapter_number=chapter_number,
                prompt=item["prompt"],
                options=options,
            )
        )
        answer_key[qid] = options[correct_index].strip().lower()

    return questions, answer_key
