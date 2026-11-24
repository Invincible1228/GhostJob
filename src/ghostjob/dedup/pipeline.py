"""3-Tier Deduplication Orchestrator & Re-post Loop Detector."""

import uuid
from datetime import datetime, timezone
from typing import Any

from ghostjob.config import settings
from ghostjob.core.models import (
    CanonicalJob,
    CanonicalStatus,
    MatchMethod,
    SnapshotToCanonical,
)
from ghostjob.db.repository import Repository
from ghostjob.dedup.exact import match_exact
from ghostjob.dedup.fuzzy import match_fuzzy
from ghostjob.dedup.semantic import match_semantic


class DeduplicationPipeline:
    """
    Processes append-only snapshots into canonical job entities.
    Tracks times_seen, times_reposted, and match confidence.
    """

    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self) -> dict[str, Any]:
        """Process all unlinked snapshots and consolidate canonical jobs."""
        unlinked = self.repo.get_snapshots_unlinked()
        if not unlinked:
            return {
                "snapshots_processed": 0,
                "new_canonical_created": 0,
                "matched_existing": 0,
                "reposts_detected": 0,
            }

        new_canonicals = 0
        matched_existing = 0
        reposts_detected = 0

        # Cache existing canonicals by company_id for speed
        company_canonicals: dict[str, list[dict]] = {}
        canonicals_to_upsert: dict[str, CanonicalJob] = {}
        links_to_insert: list[SnapshotToCanonical] = []

        for snap in unlinked:
            comp_id = snap["company_id"]
            if comp_id not in company_canonicals:
                company_canonicals[comp_id] = self.repo.get_canonical_jobs_by_company(comp_id)

            candidates = company_canonicals[comp_id]

            # Tier 1: Exact Match (Hash / External ID)
            match = match_exact(
                snapshot_external_id=snap["external_id"],
                snapshot_hash=snap["content_hash"],
                candidates=candidates,
            )

            # Tier 2: Fuzzy Rules (Title + Location compatibility)
            if not match:
                match = match_fuzzy(
                    snapshot_title=snap["title"],
                    snapshot_location=snap["location"],
                    candidates=candidates,
                    threshold=settings.fuzzy_title_threshold,
                )

            # Tier 3: Semantic Matching (Cosine overlap on title + JD excerpt)
            if not match:
                match = match_semantic(
                    snapshot_title=snap["title"],
                    snapshot_description=snap["description_text"],
                    candidates=candidates,
                    snapshot_location=snap["location"],
                    threshold=0.50,
                )

            if match:
                match.snapshot_id = snap["id"]
                links_to_insert.append(match)
                matched_existing += 1

                # Locate candidate to update state
                target_cand = next(c for c in candidates if c["id"] == match.canonical_id)
                
                # Distinguish concurrent multi-location clones from longitudinal reposts:
                snap_time = snap["scraped_at"]
                if isinstance(snap_time, str):
                    try:
                        snap_time = datetime.fromisoformat(snap_time)
                    except Exception:
                        snap_time = datetime.now(timezone.utc)

                cand_first_seen = target_cand["first_seen_at"]
                if isinstance(cand_first_seen, str):
                    try:
                        cand_first_seen = datetime.fromisoformat(cand_first_seen)
                    except Exception:
                        cand_first_seen = snap_time

                # If crawl time separation >= 24 hours, evaluate as longitudinal repost
                time_elapsed_hours = abs((snap_time - cand_first_seen).total_seconds()) / 3600.0
                is_reposted = False
                prev_ext_id = target_cand.get("active_snapshot_id")

                if time_elapsed_hours >= 24.0:
                    if prev_ext_id and prev_ext_id != snap["id"] and match.match_method != MatchMethod.EXACT_ID:
                        is_reposted = True
                        reposts_detected += 1

                # Track clone count for concurrent postings in same batch
                current_clones = target_cand.get("clone_count", 1)
                new_clone_count = current_clones + (1 if time_elapsed_hours < 24.0 else 0)
                times_reposted = target_cand.get("times_reposted", 0) + (1 if is_reposted else 0)
                
                # Queue updated canonical record
                updated_canonical = CanonicalJob(
                    id=target_cand["id"],
                    company_id=comp_id,
                    company_name=snap["company_name"],
                    title=target_cand["title"],
                    location=target_cand["location"],
                    department=target_cand.get("dept") or snap.get("dept", ""),
                    description_sample=target_cand.get("description_sample") or " ".join(snap["description_text"].split()[:250]),
                    content_hash=snap["content_hash"],
                    first_seen_at=target_cand["first_seen_at"],
                    last_seen_at=snap["scraped_at"],
                    times_seen=target_cand["times_seen"] + 1,
                    times_reposted=times_reposted,
                    clone_count=new_clone_count,
                    status=CanonicalStatus.OPEN,
                    active_snapshot_id=snap["id"],
                )
                canonicals_to_upsert[target_cand["id"]] = updated_canonical

                # Update in-memory candidate cache
                target_cand["last_seen_at"] = snap["scraped_at"]
                target_cand["times_seen"] += 1
                target_cand["times_reposted"] = times_reposted
                target_cand["clone_count"] = new_clone_count
                target_cand["active_snapshot_id"] = snap["id"]

            else:
                # Create brand new CanonicalJob
                new_canonicals += 1
                canon_id = f"cjob_{uuid.uuid4().hex[:14]}"
                desc_excerpt = " ".join(snap["description_text"].split()[:250])
                
                new_job = CanonicalJob(
                    id=canon_id,
                    company_id=comp_id,
                    company_name=snap["company_name"],
                    title=snap["title"],
                    location=snap["location"],
                    department=snap.get("dept", ""),
                    description_sample=desc_excerpt,
                    content_hash=snap["content_hash"],
                    first_seen_at=snap["scraped_at"],
                    last_seen_at=snap["scraped_at"],
                    times_seen=1,
                    times_reposted=0,
                    clone_count=1,
                    status=CanonicalStatus.OPEN,
                    active_snapshot_id=snap["id"],
                )
                canonicals_to_upsert[canon_id] = new_job

                # Queue link
                link = SnapshotToCanonical(
                    snapshot_id=snap["id"],
                    canonical_id=canon_id,
                    match_method=MatchMethod.EXACT_HASH,
                    confidence=1.0,
                )
                links_to_insert.append(link)

                # Append to cache
                company_canonicals[comp_id].append({
                    "id": canon_id,
                    "title": snap["title"],
                    "location": snap["location"],
                    "dept": snap.get("dept", ""),
                    "description_sample": desc_excerpt,
                    "content_hash": snap["content_hash"],
                    "first_seen_at": snap["scraped_at"],
                    "last_seen_at": snap["scraped_at"],
                    "times_seen": 1,
                    "times_reposted": 0,
                    "clone_count": 1,
                    "status": "open",
                    "active_snapshot_id": snap["id"],
                })

        # Batch write all updates in a single fast transaction
        self.repo.batch_commit_dedup(list(canonicals_to_upsert.values()), links_to_insert)

        return {
            "snapshots_processed": len(unlinked),
            "new_canonical_created": new_canonicals,
            "matched_existing": matched_existing,
            "reposts_detected": reposts_detected,
        }
