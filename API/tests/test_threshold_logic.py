from app.api.learning import COMPLETION_THRESHOLD, MAX_CHAPTER_ATTEMPTS


def test_threshold_constant_is_60_percent():
    assert COMPLETION_THRESHOLD == 0.60


def test_max_attempts_is_configured():
    assert MAX_CHAPTER_ATTEMPTS >= 2

