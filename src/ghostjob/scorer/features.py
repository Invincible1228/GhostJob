"""Feature extraction for ghost-job detection."""

import json
import re
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel


class FeatureVector(BaseModel):
    staleness_days: int
    times_seen: int
    times_reposted: int
    is_evergreen: bool
    jd_length_words: int
    has_salary_mention: bool
    has_concrete_tech_stack: bool
    multi_location_count: int
    company_open_roles_ratio: float


EVERGREEN_PATTERNS = [
    r"all levels",
    r"general application",
    r"future opportunities",
    r"talent pool",
    r"talent community",
    r"expression of interest",
    r"pipeline",
    r"ongoing hiring",
    r"various teams",
    r"open application",
]

SALARY_PATTERNS = [
    r"₹",
    r"rs\.?",
    r"inr",
    r"lpa",
    r"lakh",
    r"\$",
    r"usd",
    r"salary",
    r"compensation",
    r"per annum",
    r"ctc",
]

CONCRETE_TECH_KEYWORDS = [
    "python", "golang", "java", "react", "typescript", "kubernetes", "docker",
    "postgresql", "redis", "aws", "gcp", "azure", "kafka", "spark", "graphql",
    "rust", "c++", "pytorch", "tensorflow", "node.js", "django", "fastapi"
]


def parse_date(v: Any) -> datetime | None:
    if not v:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v / 1000.0, timezone.utc) if v > 1e11 else datetime.fromtimestamp(v, timezone.utc)
        except Exception:
            return None
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return None


def extract_features(
    canonical: dict[str, Any],
    all_company_jobs: list[dict[str, Any]],
    employee_count: int | None = None,
) -> FeatureVector:
    """Extract quantitative and heuristic features for a canonical job posting."""
    now = datetime.now(timezone.utc)

    dates: list[datetime] = []

    # 1. Check posted_date_claimed
    d_claimed = parse_date(canonical.get("posted_date_claimed"))
    if d_claimed:
        dates.append(d_claimed)

    # 2. Check raw_json timestamps from ATS vendors
    raw_str = canonical.get("raw_json")
    if raw_str:
        try:
            raw = json.loads(raw_str) if isinstance(raw_str, str) else raw_str
            for k in ["first_published_at", "createdAt", "publishedAt", "updated_at", "created_at"]:
                parsed = parse_date(raw.get(k))
                if parsed:
                    dates.append(parsed)
        except Exception:
            pass

    # 3. Check first_seen_at
    d_first_seen = parse_date(canonical.get("first_seen_at"))
    if d_first_seen:
        dates.append(d_first_seen)

    if dates:
        earliest_date = min(dates)
        staleness_days = max(0, (now - earliest_date).days)
    else:
        staleness_days = 0

    title = canonical.get("title", "").lower()
    desc = (canonical.get("snapshot_desc") or canonical.get("description_sample") or "").lower()

    # Evergreen heuristic check
    is_evergreen = any(re.search(pat, title) for pat in EVERGREEN_PATTERNS)
    if not is_evergreen:
        is_evergreen = any(re.search(pat, desc[:300]) for pat in EVERGREEN_PATTERNS)

    # JD text metrics
    words = desc.split()
    jd_length_words = len(words)

    has_salary = bool(re.search(r"₹|rs\.?|inr|lpa|lakh|\$|usd|salary|compensation|ctc", desc))
    has_tech = any(re.search(rf"\b{tech}\b", desc) for tech in CONCRETE_TECH_KEYWORDS)

    # Multi-location clone count (combining canonical clone_count and live company title group)
    norm_target_title = re.sub(r"\s*-\s*all levels\b", "", title, flags=re.IGNORECASE).strip()
    same_title_jobs = [
        j for j in all_company_jobs
        if re.sub(r"\s*-\s*all levels\b", "", j.get("title", "").lower(), flags=re.IGNORECASE).strip() == norm_target_title
    ]
    stored_clone_count = canonical.get("clone_count") or 1
    multi_location_count = max(stored_clone_count, len(same_title_jobs))

    # Company velocity / ratio
    total_open = len(all_company_jobs)
    if employee_count and employee_count > 0:
        ratio = round(total_open / employee_count, 3)
    else:
        ratio = 0.0

    return FeatureVector(
        staleness_days=staleness_days,
        times_seen=canonical.get("times_seen", 1),
        times_reposted=canonical.get("times_reposted", 0),
        is_evergreen=is_evergreen,
        jd_length_words=jd_length_words,
        has_salary_mention=has_salary,
        has_concrete_tech_stack=has_tech,
        multi_location_count=multi_location_count,
        company_open_roles_ratio=ratio,
    )
