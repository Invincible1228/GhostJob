"""Core domain exports."""

from ghostjob.core.models import (
    ATSType,
    CanonicalJob,
    CanonicalStatus,
    Company,
    GhostLabel,
    GhostScore,
    JobPosting,
    JobSnapshot,
    MatchMethod,
    RawJob,
    SnapshotToCanonical,
)

__all__ = [
    "ATSType",
    "CanonicalJob",
    "CanonicalStatus",
    "Company",
    "GhostLabel",
    "GhostScore",
    "JobPosting",
    "JobSnapshot",
    "MatchMethod",
    "RawJob",
    "SnapshotToCanonical",
]
