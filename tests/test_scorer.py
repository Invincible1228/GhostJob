"""Tests for ghost scoring logic and feature extraction."""

from datetime import datetime, timedelta, timezone
from ghostjob.core.models import GhostLabel
from ghostjob.scorer.engine import GhostScorerEngine
from ghostjob.scorer.features import FeatureVector, extract_features


def test_ghost_score_fresh_job():
    engine = GhostScorerEngine(repo=None)  # repo not needed for pure calculation
    feat = FeatureVector(
        staleness_days=5,
        times_seen=1,
        times_reposted=0,
        is_evergreen=False,
        jd_length_words=350,
        has_salary_mention=True,
        has_concrete_tech_stack=True,
        multi_location_count=1,
        company_open_roles_ratio=0.05,
    )
    score, label, reasons, caveats = engine.calculate_score(feat)
    assert score < 0.30
    assert label == GhostLabel.ACTIVE
    assert len(reasons) > 0


def test_ghost_score_severe_ghost():
    engine = GhostScorerEngine(repo=None)
    feat = FeatureVector(
        staleness_days=180,
        times_seen=15,
        times_reposted=4,
        is_evergreen=True,
        jd_length_words=80,
        has_salary_mention=False,
        has_concrete_tech_stack=False,
        multi_location_count=6,
        company_open_roles_ratio=0.35,
    )
    score, label, reasons, caveats = engine.calculate_score(feat)
    assert score >= 0.70
    assert label in [GhostLabel.LIKELY_GHOST, GhostLabel.ZOMBIE]
    assert any("repost loop" in r.lower() for r in reasons)
    assert any("open for" in r.lower() for r in reasons)
    assert any("locations" in r.lower() for r in reasons)


def test_feature_extraction():
    all_jobs = [
        {"title": "Software Engineer", "location": "Bangalore"},
        {"title": "Software Engineer", "location": "Delhi"},
        {"title": "Software Engineer", "location": "Hyderabad"},
    ]
    canonical = {
        "title": "Software Engineer - All Levels",
        "description_sample": "We are seeking talented engineers across India. Compensation is 25 LPA to 35 LPA. Tech: Python, AWS.",
        "first_seen_at": datetime.now(timezone.utc) - timedelta(days=95),
        "times_seen": 4,
        "times_reposted": 2,
    }
    feat = extract_features(canonical, all_jobs, employee_count=100)
    assert feat.staleness_days >= 94
    assert feat.is_evergreen is True
    assert feat.has_salary_mention is True
    assert feat.has_concrete_tech_stack is True
    assert feat.multi_location_count == 3
