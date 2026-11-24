"""Tier 1 Deduplication: Exact External ID & SHA-256 Content Hash Matching."""

from ghostjob.core.models import MatchMethod, SnapshotToCanonical


def match_exact(
    snapshot_external_id: str,
    snapshot_hash: str,
    candidates: list[dict],
) -> SnapshotToCanonical | None:
    """
    Tier 1: Check for exact match against known canonical jobs.
    Highest precedence:
    1. Exact content hash match (confidence = 1.0)
    2. Same external_id under the same company (confidence = 1.0)
    """
    # 1. Exact content hash match
    for cand in candidates:
        if cand.get("content_hash") and cand["content_hash"] == snapshot_hash:
            return SnapshotToCanonical(
                snapshot_id="",  # Populated by pipeline
                canonical_id=cand["id"],
                match_method=MatchMethod.EXACT_HASH,
                confidence=1.0,
            )

    # 2. Check external_id match via active snapshot or historical link
    for cand in candidates:
        if cand.get("external_id") == snapshot_external_id:
            return SnapshotToCanonical(
                snapshot_id="",
                canonical_id=cand["id"],
                match_method=MatchMethod.EXACT_ID,
                confidence=1.0,
            )

    return None
