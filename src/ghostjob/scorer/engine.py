"""Transparent explainable ghost-job heuristic scoring engine."""

from datetime import datetime, timezone
from typing import Any

from ghostjob.config import settings
from ghostjob.core.models import CanonicalJob, GhostLabel, GhostScore
from ghostjob.db.repository import Repository
from ghostjob.scorer.features import FeatureVector, extract_features


class GhostScorerEngine:
    """Computes explainable ghost-job probability scores with human-readable rationale."""

    def __init__(self, repo: Repository):
        self.repo = repo

    def calculate_score(
        self,
        features: FeatureVector,
        median_company_close_days: int = 40,
    ) -> tuple[float, GhostLabel, list[str], list[str]]:
        """
        Evaluate features using transparent weighted signals.
        Returns: (probability_score, label, reasons, caveats)
        """
        reasons: list[str] = []
        caveats: list[str] = []

        # 1. Staleness signal
        # Benchmark against typical healthy time-to-close (40 days)
        if features.staleness_days > 90:
            s_staleness = 1.0
            reasons.append(
                f"Open for {features.staleness_days} days based on native ATS timestamp (exceeds typical {median_company_close_days}-day hiring cycle)"
            )
        elif features.staleness_days > 60:
            s_staleness = 0.75 + min(0.25, (features.staleness_days - 60) / 120.0)
            reasons.append(
                f"Open {features.staleness_days} days, exceeding typical {median_company_close_days}-day hiring cycle"
            )
        elif features.staleness_days > 35:
            s_staleness = min(0.70, (features.staleness_days - 35) / 50.0)
            reasons.append(
                f"Open {features.staleness_days} days, exceeding typical {median_company_close_days}-day hiring cycle"
            )
        else:
            s_staleness = 0.0

        # 2. Repost loop signal (strongest single signal)
        if features.times_reposted >= 3:
            s_repost = 1.0
            reasons.append(
                f"Detected severe repost loop: role republished {features.times_reposted} times with reset posting timestamps"
            )
        elif features.times_reposted >= 1:
            s_repost = 0.6 + (features.times_reposted * 0.15)
            reasons.append(
                f"Reposted {features.times_reposted} time(s) with new external posting identifier"
            )
        else:
            s_repost = 0.0

        # 3. Evergreen / pipeline farming signal
        if features.is_evergreen:
            s_evergreen = 0.85
            reasons.append("Job title or description matches evergreen talent pool / open requisition template")
        else:
            s_evergreen = 0.0

        # 4. JD Quality & Specificity (mitigates or increases ghost risk)
        s_jd = 0.0
        if not features.has_concrete_tech_stack and features.jd_length_words < 120:
            s_jd = 0.6
            reasons.append("Vague job description without specific tech stack or tooling requirements")
        elif not features.has_concrete_tech_stack:
            s_jd = 0.3
            caveats.append("Lacks explicit tooling/tech stack keywords")

        if not features.has_salary_mention:
            caveats.append("No salary band or compensation range listed")

        # 5. Multi-location clone blast
        if features.multi_location_count >= 5:
            s_clone = 0.9
            reasons.append(
                f"Identical JD simultaneously active across {features.multi_location_count} separate locations"
            )
        elif features.multi_location_count >= 3:
            s_clone = 0.5
            reasons.append(
                f"Cross-posted across {features.multi_location_count} locations"
            )
        elif features.multi_location_count >= 2:
            s_clone = 0.25
        else:
            s_clone = 0.0

        # Weighted combination
        raw_score = (
            s_staleness * settings.staleness_weight +
            s_repost * settings.repost_loop_weight +
            s_evergreen * settings.evergreen_weight +
            s_jd * settings.jd_quality_weight +
            s_clone * settings.location_clone_weight
        )

        # Compound Interaction Boosts for real-world single-snapshot signals
        if features.staleness_days > 85:
            raw_score += 0.36
        elif features.staleness_days > 60 and (
            features.multi_location_count >= 3 or features.is_evergreen or (features.jd_length_words < 120 and not features.has_concrete_tech_stack)
        ):
            raw_score += 0.36
            reasons.append(
                "Elevated risk: extended requisition age (>60 days) combined with multi-city cloning, evergreen pattern, or thin JD"
            )
        elif features.staleness_days > 45 and (features.multi_location_count >= 3 or features.is_evergreen):
            raw_score += 0.20

        final_score = round(min(1.0, max(0.0, raw_score)), 2)

        # Assign discrete label
        if final_score >= 0.70:
            if features.staleness_days > 180 and (
                features.multi_location_count >= 2 or features.is_evergreen or features.times_reposted >= 1 or features.staleness_days > 270
            ):
                label = GhostLabel.ZOMBIE
                reasons.append("Extreme staleness (>180 days open) indicates abandoned zombie requisition")
            else:
                label = GhostLabel.LIKELY_GHOST
        elif final_score >= 0.35:
            label = GhostLabel.AGING
        else:
            label = GhostLabel.ACTIVE
            if not reasons:
                reasons.append("Recently posted listing with healthy recruitment indicators")

        return final_score, label, reasons, caveats

    def score_all_jobs(self) -> dict[str, Any]:
        """Score all canonical jobs in the database and save explanations."""
        all_canonicals = self.repo.get_all_canonical_jobs()
        if not all_canonicals:
            return {"total_scored": 0, "distribution": {}}

        # Group by company for context
        by_company: dict[str, list[dict]] = {}
        for cj in all_canonicals:
            by_company.setdefault(cj["company_id"], []).append(cj)

        scored_count = 0
        distribution: dict[str, int] = {
            GhostLabel.ACTIVE.value: 0,
            GhostLabel.AGING.value: 0,
            GhostLabel.LIKELY_GHOST.value: 0,
            GhostLabel.ZOMBIE.value: 0,
        }

        scores_to_insert: list[GhostScore] = []
        for cj in all_canonicals:
            comp_jobs = by_company.get(cj["company_id"], [])
            emp_count = cj.get("employee_count")

            feat = extract_features(cj, comp_jobs, emp_count)
            score, label, reasons, caveats = self.calculate_score(feat)

            ghost_score = GhostScore(
                canonical_id=cj["id"],
                scored_at=datetime.now(timezone.utc),
                score=score,
                label=label,
                reasons=reasons,
                signals=feat.model_dump(),
                caveats=caveats,
            )
            scores_to_insert.append(ghost_score)
            scored_count += 1
            distribution[label.value] += 1

        if scores_to_insert:
            self.repo.insert_ghost_scores_batch(scores_to_insert)

        return {
            "total_scored": scored_count,
            "distribution": distribution,
        }
