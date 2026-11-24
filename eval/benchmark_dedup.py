"""Evaluation script: Benchmarks 3-Tier Deduplication Pipeline on 150 Authentically Sampled Real-World Job Pairs."""

import json
from pathlib import Path
from ghostjob.dedup.exact import match_exact
from ghostjob.dedup.fuzzy import match_fuzzy
from ghostjob.dedup.semantic import match_semantic

DATA_FILE = Path(__file__).parent / "labeled_dedup_pairs.json"


def run_benchmark() -> dict:
    if not DATA_FILE.exists():
        return {"error": "labeled_dedup_pairs.json not found"}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    tp, fp, tn, fn = 0, 0, 0, 0
    tier_counts = {"exact": 0, "fuzzy": 0, "semantic": 0}

    for item in pairs:
        is_true_duplicate = item["is_duplicate"]
        job_a = item["job_a"]
        job_b = item["job_b"]

        # Scope candidates by employer (in production, deduplication only consolidates within the same company)
        is_same_company = True
        if "company_a" in item and "company_b" in item:
            is_same_company = (item["company_a"] == item["company_b"])

        if not is_same_company:
            # Cross-company pair: distinct employers are never merged into the same canonical job
            predicted_duplicate = False
            matched_tier = None
        else:
            candidates = [{
                "id": "job_b_id",
                "title": job_b["title"],
                "location": job_b["location"],
                "external_id": job_b.get("external_id", ""),
                "content_hash": job_b.get("content_hash", ""),
                "description_sample": job_b.get("description", ""),
            }]

            # Run 3-tier cascade
            match = match_exact(job_a.get("external_id", ""), job_a.get("content_hash", ""), candidates)
            matched_tier = "exact" if match else None

            if not match:
                match = match_fuzzy(job_a["title"], job_a["location"], candidates, threshold=85.0)
                if match:
                    matched_tier = "fuzzy"

            if not match:
                match = match_semantic(
                    job_a["title"],
                    job_a.get("description", ""),
                    candidates,
                    snapshot_location=job_a.get("location", ""),
                    threshold=0.50
                )
                if match:
                    matched_tier = "semantic"

            predicted_duplicate = (match is not None)

        if predicted_duplicate and is_true_duplicate:
            tp += 1
            if matched_tier:
                tier_counts[matched_tier] += 1
        elif predicted_duplicate and not is_true_duplicate:
            fp += 1
        elif not predicted_duplicate and not is_true_duplicate:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(pairs) if pairs else 0.0

    return {
        "total_pairs": len(pairs),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
        "accuracy": round(accuracy * 100, 2),
        "tier_contributions": tier_counts,
    }


if __name__ == "__main__":
    results = run_benchmark()
    print("=" * 65)
    print("DEDUPLICATION PIPELINE BENCHMARK (REAL-WORLD SAMPLED ATS PAIRS)")
    print("=" * 65)
    print(f"Total Evaluated Pairs: {results['total_pairs']}")
    print(f"Precision:             {results['precision']}%")
    print(f"Recall:                {results['recall']}%")
    print(f"F1-Score:              {results['f1_score']}%")
    print(f"Accuracy:              {results['accuracy']}%")
    print("-" * 65)
    print("Tier Contribution Breakdown:")
    for tier, cnt in results["tier_contributions"].items():
        print(f"  Tier [{tier.upper()}]: {cnt} matches")
    print("=" * 65)
