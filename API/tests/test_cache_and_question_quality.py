from app.api.learning import (
    TestQuestion as LearningTestQuestion,
    _chapter_test_cache_key,
    _dedupe_generated_questions,
    _question_set_is_high_quality,
    _reading_content_is_high_quality,
    _section_content_cache_key,
)


def test_section_content_cache_key_is_stable_across_profile_changes():
    k1 = _section_content_cache_key("1.1", "simple_supportive", "c5m2")
    k2 = _section_content_cache_key("1.1", "concise_challenging", "c9m8")
    assert k1 == k2
    assert "stable" in k1


def test_chapter_test_cache_key_is_stable_across_difficulty_changes():
    k1 = _chapter_test_cache_key("__chapter__", "foundational", "c2m1")
    k2 = _chapter_test_cache_key("__chapter__", "advanced", "c9m9")
    assert k1 == k2
    assert "stable" in k1


def test_dedupe_filters_duplicates_irrelevant_and_invalid_options():
    raw = [
        {
            "q": "Which statement is true for linear equations in two variables?",
            "options": ["A valid relation", "Wrong 1", "Wrong 2", "Wrong 3"],
            "correct": 0,
        },
        {
            "q": "Which statement is true for linear equations in two variables?",
            "options": ["A valid relation", "Wrong 1", "Wrong 2", "Wrong 3"],
            "correct": 0,
        },
        {
            "q": "What is photosynthesis in plants?",
            "options": ["A", "B", "C", "D"],
            "correct": 0,
        },
        {
            "q": "Solve x + y = 10 and x - y = 2.",
            "options": ["x=6,y=4", "x=4,y=6", "x=5,y=5", "x=7,y=3"],
            "correct": 0,
        },
        {
            "q": "A malformed question",
            "options": ["same", "same", "same", "same"],
            "correct": 0,
        },
    ]
    out, removed = _dedupe_generated_questions(
        raw,
        target_count=10,
        chapter_name="Linear Equations in Two Variables",
        topic_titles=["Graphical solution", "Substitution method"],
    )
    prompts = [q["q"] for q in out]
    assert len(out) == 2
    assert removed >= 3
    assert any("linear equations" in p.lower() for p in prompts)
    assert any("solve x + y = 10" in p.lower() for p in prompts)


def test_reading_quality_gate_rejects_placeholder_content():
    bad = "# Intro\n\nCorrect definition of topic.\nIncorrect variant."
    good = (
        "# Linear Equations\n\n"
        "A linear equation in two variables has the form ax + by + c = 0. "
        "To solve, first isolate one variable and substitute into the second equation. "
        "Check the ordered pair in both equations and interpret the point as intersection of two lines. "
        "This method avoids guessing and gives a logically verifiable answer."
    )
    assert _reading_content_is_high_quality(bad, "Linear Equations", ["Substitution method"]) is False
    assert _reading_content_is_high_quality(good, "Linear Equations", ["Substitution method"]) is True


def test_question_set_quality_gate_rejects_low_quality_stems():
    bad_questions = [
        LearningTestQuestion(question_id="q1", prompt="Which concept is central to Introduction?", options=["A", "B", "C", "D"], chapter_number=1),
        LearningTestQuestion(question_id="q2", prompt="Select the statement that best matches Introduction.", options=["A", "B", "C", "D"], chapter_number=1),
        LearningTestQuestion(question_id="q3", prompt="Select the statement that best matches Introduction.", options=["A", "B", "C", "D"], chapter_number=1),
        LearningTestQuestion(question_id="q4", prompt="Select the statement that best matches Introduction.", options=["A", "B", "C", "D"], chapter_number=1),
    ]
    good_questions = [
        LearningTestQuestion(question_id="q1", prompt="Solve x + y = 7 and x - y = 1.", options=["x=4,y=3", "x=3,y=4", "x=5,y=2", "x=2,y=5"], chapter_number=1),
        LearningTestQuestion(question_id="q2", prompt="Which pair satisfies 2x + y = 9?", options=["(3,3)", "(2,5)", "(4,1)", "(1,7)"], chapter_number=1),
        LearningTestQuestion(question_id="q3", prompt="Which method is suitable to solve x = 2y and x + y = 9?", options=["Substitution", "Factorization", "Mensuration", "Probability"], chapter_number=1),
        LearningTestQuestion(question_id="q4", prompt="If x + y = 10 and y = 6, find x.", options=["4", "6", "10", "16"], chapter_number=1),
    ]
    assert _question_set_is_high_quality(
        bad_questions,
        chapter_name="Linear Equations in Two Variables",
        topic_titles=["Graphical Method"],
        min_count=4,
    ) is False
    assert _question_set_is_high_quality(
        good_questions,
        chapter_name="Linear Equations in Two Variables",
        topic_titles=["Graphical Method"],
        min_count=4,
    ) is True
