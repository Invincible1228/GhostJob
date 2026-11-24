"""Dataset export utilities for CSV and JSON distributions."""

import csv
import json
from pathlib import Path
from typing import Any

from ghostjob.db.repository import Repository


def export_dataset(
    repo: Repository,
    output_path: Path,
    file_format: str = "json",
) -> int:
    """Export all canonical jobs with latest ghost scores to a file."""
    jobs = repo.get_all_canonical_jobs()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for j in jobs:
        reasons = []
        if j.get("reasons_json"):
            try:
                reasons = json.loads(j["reasons_json"])
            except Exception:
                reasons = []

        records.append({
            "canonical_id": j["id"],
            "company_name": j["company_name"],
            "company_domain": j["company_domain"],
            "title": j["title"],
            "location": j["location"],
            "department": j.get("dept", ""),
            "status": j["status"],
            "first_seen_at": str(j["first_seen_at"]),
            "last_seen_at": str(j["last_seen_at"]),
            "times_seen": j["times_seen"],
            "times_reposted": j["times_reposted"],
            "ghost_score": j.get("latest_ghost_score") or 0.0,
            "ghost_label": j.get("latest_ghost_label") or "active",
            "reasons": "; ".join(reasons) if file_format == "csv" else reasons,
        })

    if file_format.lower() == "csv":
        if not records:
            fieldnames = [
                "canonical_id", "company_name", "company_domain", "title", "location",
                "department", "status", "first_seen_at", "last_seen_at", "times_seen",
                "times_reposted", "ghost_score", "ghost_label", "reasons"
            ]
        else:
            fieldnames = list(records[0].keys())

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)

    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    return len(records)
