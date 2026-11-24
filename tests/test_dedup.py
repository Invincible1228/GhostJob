"""Tests for 3-tier deduplication pipeline."""

from ghostjob.dedup.exact import match_exact
from ghostjob.dedup.fuzzy import match_fuzzy
from ghostjob.dedup.semantic import match_semantic
from ghostjob.dedup.normalizer import normalize_location, normalize_title, are_locations_compatible


def test_normalizers():
    assert normalize_title("Senior Software Engineer (Remote) [Urgently Hiring]") == "senior software engineer"
    assert normalize_title("SDE-2 - Backend") == "software development engineer ii backend"
    assert normalize_location("Bangalore, Karnataka") == "bengaluru"
    assert normalize_location("BLR Office") == "bengaluru"
    assert normalize_location("Gurugram / Noida") == "delhi_ncr"
    assert are_locations_compatible("Bangalore", "Bengaluru") is True
    assert are_locations_compatible("Bangalore", "Remote") is True
    assert are_locations_compatible("Mumbai", "Chennai") is False


def test_exact_match():
    candidates = [
        {"id": "c1", "content_hash": "hash123", "external_id": "ext-1"},
        {"id": "c2", "content_hash": "hash456", "external_id": "ext-2"},
    ]
    # Exact content hash
    m = match_exact("ext-999", "hash123", candidates)
    assert m is not None
    assert m.canonical_id == "c1"
    assert m.confidence == 1.0


def test_fuzzy_match():
    candidates = [
        {"id": "c1", "title": "Staff Software Engineer - Backend", "location": "Bengaluru"},
        {"id": "c2", "title": "Product Marketing Manager", "location": "Mumbai"},
    ]
    # Slight title variation and alias location
    m = match_fuzzy("Staff Software Engineer (Backend)", "Bangalore", candidates, threshold=85.0)
    assert m is not None
    assert m.canonical_id == "c1"
    assert m.confidence > 0.90


def test_semantic_match():
    candidates = [
        {
            "id": "c1",
            "title": "Machine Learning Engineer",
            "description_sample": "Design deep learning architectures with PyTorch, distributed training on Kubernetes and GPUs.",
        }
    ]
    # Same intent with rephrased title & description
    m = match_semantic(
        "AI / ML Systems Engineer",
        "Build and scale deep learning models using PyTorch on Kubernetes infrastructure and GPU clusters.",
        candidates,
        threshold=0.35,
    )
    assert m is not None
    assert m.canonical_id == "c1"
    assert m.confidence >= 0.35
