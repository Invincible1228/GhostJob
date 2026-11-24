"""Heuristic Sensitivity & Synthetic Stress-Test Benchmark.

Evaluates the ghost-job scoring engine's mathematical separability across
a controlled 250-listing synthetic stress-test cohort with defined risk profiles:
- Fresh healthy postings (low risk baseline)
- Stagnant aging postings (moderate risk)
- Severe multi-signal ghost candidates (extreme staleness, evergreen templates, multi-city clones)

Note on Ground Truth: Genuine empirical ground-truth closure outcomes require
longitudinal time-series crawls over 30-60 days. Our automated daily GitHub Actions
workflow (.github/workflows/crawl.yml) is continuously building this time-series
database. This benchmark evaluates the scoring model's feature separability.
"""

from ghostjob.scorer.engine import GhostScorerEngine
from ghostjob.scorer.features import FeatureVector


def run_ghost_evaluation() -> dict:
    engine = GhostScorerEngine(repo=None)

    cohort = []
    
    # 1. 100 Low-Risk Healthy Listings (Fresh, specific tech requirements, single city)
    for i in range(100):
        cohort.append({
            "expected_high_risk": False,
            "features": FeatureVector(
                staleness_days=5 + (i % 25),
                times_seen=1 + (i % 3),
                times_reposted=0,
                is_evergreen=False,
                jd_length_words=320,
                has_salary_mention=(i % 3 == 0),
                has_concrete_tech_stack=True,
                multi_location_count=1,
                company_open_roles_ratio=0.03,
            )
        })

    # 2. 80 High-Risk Synthetic Ghost Candidates (Open > 120 days, evergreen, multi-city clones)
    for i in range(80):
        cohort.append({
            "expected_high_risk": True,
            "features": FeatureVector(
                staleness_days=95 + (i % 90),
                times_seen=10 + (i % 8),
                times_reposted=2 + (i % 3),
                is_evergreen=(i % 2 == 0),
                jd_length_words=95,
                has_salary_mention=False,
                has_concrete_tech_stack=(i % 4 == 0),
                multi_location_count=3 + (i % 4),
                company_open_roles_ratio=0.18,
            )
        })

    # 3. 70 Moderate / Aging Borderline Postings (Open 40-70 days, standard JD)
    for i in range(70):
        is_elevated = (i % 3 == 0)
        cohort.append({
            "expected_high_risk": is_elevated,
            "features": FeatureVector(
                staleness_days=40 + (i % 30),
                times_seen=3 + (i % 3),
                times_reposted=(1 if is_elevated else 0),
                is_evergreen=False,
                jd_length_words=220,
                has_salary_mention=False,
                has_concrete_tech_stack=True,
                multi_location_count=1 + (i % 2),
                company_open_roles_ratio=0.07,
            )
        })

    # Evaluate all cohort listings
    scored = []
    for item in cohort:
        score, label, reasons, caveats = engine.calculate_score(item["features"])
        scored.append({
            "score": score,
            "label": label.value,
            "expected_high_risk": item["expected_high_risk"]
        })

    # Precision@top-20%
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_k_count = int(len(scored) * 0.20)
    top_k = scored[:top_k_count]
    true_high_risk_in_top_k = sum(1 for x in top_k if x["expected_high_risk"])
    precision_at_top_20 = (true_high_risk_in_top_k / top_k_count) * 100.0

    # Classification at threshold >= 0.50
    tp = sum(1 for x in scored if x["score"] >= 0.50 and x["expected_high_risk"])
    fp = sum(1 for x in scored if x["score"] >= 0.50 and not x["expected_high_risk"])
    tn = sum(1 for x in scored if x["score"] < 0.50 and not x["expected_high_risk"])
    fn = sum(1 for x in scored if x["score"] < 0.50 and x["expected_high_risk"])

    precision = (tp / (tp + fp) * 100) if (tp + fp) else 0.0
    recall = (tp / (tp + fn) * 100) if (tp + fn) else 0.0
    fpr = (fp / (fp + tn) * 100) if (fp + tn) else 0.0

    return {
        "total_cohort_size": len(scored),
        "precision_at_top_20": round(precision_at_top_20, 2),
        "threshold_precision": round(precision, 2),
        "threshold_recall": round(recall, 2),
        "false_positive_rate": round(fpr, 2),
        "high_risk_count": sum(1 for x in scored if x["score"] >= 0.70),
    }


if __name__ == "__main__":
    res = run_ghost_evaluation()
    print("=" * 65)
    print("GHOST SCORER CONTROLLED SENSITIVITY BENCHMARK (N=250)")
    print("=" * 65)
    print(f"Total Cohort Size:      {res['total_cohort_size']}")
    print(f"Precision@top-20%:      {res['precision_at_top_20']}%")
    print(f"Classification Prec:    {res['threshold_precision']}%")
    print(f"Classification Recall:  {res['threshold_recall']}%")
    print(f"False Positive Rate:    {res['false_positive_rate']}%")
    print(f"High-Risk Ghost Count:  {res['high_risk_count']}")
    print("=" * 65)
