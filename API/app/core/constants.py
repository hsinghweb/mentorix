"""
Domain constants — named constants for learning-domain thresholds and weights.

Centralises magic numbers previously scattered across route handlers and agent
classes.  Import from here to keep numeric policy auditable in one place.
"""
from __future__ import annotations


# ── Mastery bands ────────────────────────────────────────────────────

MASTERY_WEAK_THRESHOLD = 0.40
"""Mastery below this is classified as 'beginner'."""

MASTERY_DEVELOPING_THRESHOLD = 0.60
"""Mastery below this (but >= weak) is classified as 'developing'."""

MASTERY_PROFICIENT_THRESHOLD = 0.80
"""Mastery at or above this is classified as 'mastered'."""

COMPLETION_THRESHOLD = 0.60
"""60% score required to pass a chapter/section test."""


# ── Timeline bounds ──────────────────────────────────────────────────

TIMELINE_MIN_WEEKS = 14
"""Minimum allowed learning timeline length (weeks)."""

TIMELINE_MAX_WEEKS = 28
"""Maximum allowed learning timeline length (weeks)."""

MAX_CHAPTER_ATTEMPTS = 2
"""Maximum number of test attempts per chapter before forced advancement."""


# ── Ability-to-tone mapping thresholds ───────────────────────────────

ABILITY_WEAK_BOUND = 0.4
"""Ability below this maps to simple_supportive tone."""

ABILITY_STRONG_BOUND = 0.7
"""Ability at or above this maps to concise_challenging tone."""


# ── Scoring weights ─────────────────────────────────────────────────

ABILITY_BASE_WEIGHT = 0.3
"""Base weight in ability calculation (e.g. 0.3 + 0.7 * ability)."""

ABILITY_SCALE_WEIGHT = 0.7
"""Scale weight multiplied by raw ability score."""


# ── Mastery blending (ReflectionAgent) ───────────────────────────────

OLD_MASTERY_WEIGHT = 0.7
"""Weight given to existing mastery when blending with new score."""

NEW_SCORE_WEIGHT = 0.3
"""Weight given to current assessment score when blending."""


# ── Engagement adjustment (ReflectionAgent) ──────────────────────────

ENGAGEMENT_BOOST = 0.05
"""Engagement score increase for strong performance."""

ENGAGEMENT_PENALTY = -0.03
"""Engagement score decrease for weak performance."""

PERFORMANCE_THRESHOLD = 0.6
"""Score threshold separating positive from negative adjustments."""


# ── Retention decay bounds (ReflectionAgent) ─────────────────────────

RETENTION_DECAY_IMPROVE = 0.97
"""Multiplicative retention decay improvement factor for good scores."""

RETENTION_DECAY_DEGRADE = 1.03
"""Multiplicative retention decay degradation factor for poor scores."""

RETENTION_DECAY_MIN = 0.02
"""Minimum allowed retention decay value."""

RETENTION_DECAY_MAX = 0.5
"""Maximum allowed retention decay value."""


# ── Onboarding risk thresholds ───────────────────────────────────────

HIGH_RISK_MASTERY = 0.4
"""Average mastery below this triggers high risk classification."""

MEDIUM_RISK_MASTERY = 0.65
"""Average mastery below this triggers medium risk classification."""

WEAK_CONCEPT_THRESHOLD = 0.5
"""Concepts below this mastery are classified as weak."""


# ── Content quality ──────────────────────────────────────────────────

MIN_CONTENT_WORDS = 45
"""Minimum word count for reading content to be considered high quality."""

NEAR_DUPLICATE_THRESHOLD = 0.9
"""SequenceMatcher ratio threshold for near-duplicate question detection."""

MIN_MCQ_OPTIONS = 4
"""Minimum number of distinct options required for a valid MCQ question."""


# ── Prompt versions ──────────────────────────────────────────────────

CONTENT_PROMPT_VERSION = "v2"
"""Version tag for content generation prompts, used in cache keys."""

TEST_PROMPT_VERSION = "v2"
"""Version tag for test generation prompts, used in cache keys."""


# ── Assessment scoring (AssessmentAgent) ─────────────────────────────

ASSESSMENT_CORRECT_SCORE = 1.0
"""Score assigned for a fully correct answer."""

ASSESSMENT_PARTIAL_SCORE = 0.6
"""Score assigned for a partially correct answer."""

ASSESSMENT_INCORRECT_SCORE = 0.35
"""Score assigned for an incorrect answer."""


# ── Circuit breaker defaults ─────────────────────────────────────────

AGENT_FAILURE_THRESHOLD = 3
"""Consecutive failures before opening an agent circuit breaker."""

AGENT_COOLDOWN_SECONDS = 30.0
"""Seconds to wait before allowing a trial request (half-open state)."""
