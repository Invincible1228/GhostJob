"""Tier 2 Deduplication: Fuzzy Title + Compatible Location Matching."""

from rapidfuzz import fuzz

from ghostjob.core.models import MatchMethod, SnapshotToCanonical
from ghostjob.dedup.normalizer import are_locations_compatible, normalize_title


def match_fuzzy(
    snapshot_title: str,
    snapshot_location: str,
    candidates: list[dict],
    threshold: float = 88.0,
) -> SnapshotToCanonical | None:
    """
    Tier 2: Fast RapidFuzz token_sort_ratio comparison.
    Requires:
    1. High title similarity (>= threshold)
    2. Location compatibility (same canonical city or remote)
    """
    norm_title = normalize_title(snapshot_title)
    best_cand = None
    best_ratio = 0.0

    for cand in candidates:
        cand_norm_title = normalize_title(cand["title"])
        
        # Check location compatibility
        if not are_locations_compatible(snapshot_location, cand.get("location", "")):
            continue

        ratio = fuzz.token_sort_ratio(norm_title, cand_norm_title)
        if ratio >= threshold and ratio > best_ratio:
            best_ratio = ratio
            best_cand = cand

    if best_cand is not None:
        return SnapshotToCanonical(
            snapshot_id="",
            canonical_id=best_cand["id"],
            match_method=MatchMethod.FUZZY_RULES,
            confidence=round(best_ratio / 100.0, 3),
        )

    return None
