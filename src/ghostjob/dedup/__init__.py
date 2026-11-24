"""Deduplication module exports."""

from ghostjob.dedup.exact import match_exact
from ghostjob.dedup.fuzzy import match_fuzzy
from ghostjob.dedup.semantic import match_semantic
from ghostjob.dedup.pipeline import DeduplicationPipeline

__all__ = [
    "match_exact",
    "match_fuzzy",
    "match_semantic",
    "DeduplicationPipeline",
]
