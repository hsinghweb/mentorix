# Research Evaluation Guide

This document explains how to evaluate the Mentorix adaptive tutoring system using the built-in outcome analytics and A/B testing framework.

---

## 1. Evaluation Metrics

All metrics are computed by `services/outcome_analytics.py` and accessible via the `/analytics/` API.

### Per-Learner Metrics

| Metric | Description | Computation |
|--------|-------------|-------------|
| **Mastery Growth Rate** | Weekly mastery improvement | `(current_avg_mastery - diagnostic_score) / weeks_active` |
| **Completion Velocity** | Chapters completed per week | `chapters_completed / weeks_active` |
| **Diagnostic-to-Current Delta** | Pre/post mastery improvement | `current_avg_mastery - diagnostic_score` |
| **Trajectory** | Learning direction | `improving` (delta > 0.1), `stable`, `declining` (delta < -0.05) |
| **Risk Level** | At-risk classification | Based on mastery < 0.4 OR (velocity < 0.5 AND completion < 30%) |

### Cohort Metrics

| Metric | Description |
|--------|-------------|
| **Average Mastery Growth** | Mean mastery growth rate across all learners |
| **Trajectory Distribution** | Count of improving / stable / declining learners |
| **At-Risk Count** | Learners classified as high risk |
| **Average Completion** | Mean chapter completion percentage |

---

## 2. A/B Testing Framework

The framework (`services/ab_testing.py`) provides 4 built-in experiments:

| Experiment | Groups | Hypothesis |
|-----------|--------|-----------|
| `content_difficulty` | adaptive, fixed_medium | Adaptive difficulty improves mastery growth |
| `tone_strategy` | supportive, neutral, challenging | Tone affects engagement and retention |
| `revision_frequency` | aggressive, standard, relaxed | Revision frequency affects long-term retention |
| `explanation_style` | analogy_heavy, direct, mixed | Analogies improve concept understanding |

### Assignment Method

Learners are assigned to groups via **consistent hashing** (`SHA-256(learner_id:experiment_id) % group_count`). This ensures:
- Same learner always gets the same group (deterministic)
- Groups are approximately balanced (uniform distribution)
- No database writes needed for assignment

### Tracking Events

Call `track_experiment_event()` after key learning events:

```python
from app.services.ab_testing import track_experiment_event

# After test completion
track_experiment_event(
    learner_id=str(learner_id),
    experiment_id="content_difficulty",
    event_type="test_score",
    value=score,
    metadata={"chapter": chapter_number},
)
```

---

## 3. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analytics/outcomes` | GET | Cohort summary |
| `/analytics/outcomes/{learner_id}` | GET | Individual learner metrics |
| `/analytics/export` | GET | CSV download of all outcomes |
| `/analytics/experiments` | GET | List all experiments |
| `/analytics/experiments/{id}` | GET | Detailed experiment results |

---

## 4. Running an Evaluation

### Step 1: Deploy and collect data

```bash
docker compose up -d
# Wait for students to use the system
```

### Step 2: Export outcome data

```bash
curl http://localhost:8000/analytics/export > outcomes.csv
```

### Step 3: Analyse results

```python
import pandas as pd

df = pd.read_csv("outcomes.csv")

# Overall effectiveness
print(f"Average mastery growth: {df['mastery_growth_rate'].mean():.4f}")
print(f"Improving: {(df['trajectory'] == 'improving').sum()}")
print(f"At-risk: {(df['risk_level'] == 'high').sum()}")

# Pre/post comparison
print(f"Diagnostic mean: {df['diagnostic_score'].mean():.2f}")
print(f"Current mastery mean: {df['current_avg_mastery'].mean():.2f}")
print(f"Delta: {df['diagnostic_to_current_delta'].mean():.4f}")
```

### Step 4: A/B test analysis

```bash
curl http://localhost:8000/analytics/experiments/content_difficulty | python -m json.tool
```

---

## 5. Template for Results Section

> **Evaluation Results**: We deployed Mentorix to N students over M weeks.
> The average mastery growth rate was X per week. Y% of learners showed
> improving trajectories. The diagnostic-to-current mastery delta was Z,
> indicating [significant/modest] learning gains. A/B testing of content
> difficulty strategies showed that [adaptive/fixed] difficulty resulted
> in W% higher mastery growth (p < 0.05).

---

## 6. Limitations

- **No control group without tutoring**: All learners use the system (compare with historical exam data)
- **Self-selection bias**: Voluntary participation may skew results
- **Small sample risk**: Ensure N ≥ 30 for statistical power
- **Confounding variables**: Time of day, prior knowledge, motivation not fully controlled
