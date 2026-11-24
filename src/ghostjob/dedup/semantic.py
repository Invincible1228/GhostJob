"""Tier 3 Deduplication: Semantic Document Cosine Matching."""

import math
import re
from collections import Counter
from rapidfuzz import fuzz

from ghostjob.core.models import MatchMethod, SnapshotToCanonical
from ghostjob.dedup.normalizer import are_locations_compatible, normalize_title

STOPWORDS = {
    "and", "or", "in", "on", "with", "for", "to", "of", "a", "an", "the",
    "at", "by", "from", "as", "is", "are", "we", "our", "you", "your", "will",
    "be", "have", "has", "must", "with", "this", "that", "these", "those",
    "about", "company", "team", "work", "role", "looking", "join"
}

# Domain words that indicate mutually exclusive specializations within tech
DISJOINT_ROLE_PAIRS = [
    ("frontend", "backend"),
    ("ios", "android"),
    ("intern", "staff"),
    ("intern", "senior"),
    ("intern", "principal"),
    ("staff", "junior"),
    ("staff", "engineer i"),
    ("staff", "sde 1"),
    ("staff", "sde i"),
    ("designer", "manager"),
    ("analyst", "scientist"),
    ("qa", "devops"),
    ("legal", "security"),
    ("sales", "engineering"),
]


def tokenize(text: str) -> list[str]:
    """Tokenize text into informative unigrams, filtering out stopwords."""
    clean = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return [w for w in clean.split() if len(w) >= 2 and w not in STOPWORDS]


def compute_cosine_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity over term frequencies."""
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    if not tokens1 or not tokens2:
        return 0.0

    vec1 = Counter(tokens1)
    vec2 = Counter(tokens2)

    intersection = set(vec1.keys()) & set(vec2.keys())
    dot_product = sum(vec1[x] * vec2[x] for x in intersection)

    norm1 = math.sqrt(sum(v * v for v in vec1.values()))
    norm2 = math.sqrt(sum(v * v for v in vec2.values()))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot_product / (norm1 * norm2)


def match_semantic(
    snapshot_title: str,
    snapshot_description: str,
    candidates: list[dict],
    snapshot_location: str = "",
    threshold: float = 0.50,
) -> SnapshotToCanonical | None:
    """
    Tier 3: Semantic document comparison across title and description excerpt.
    Enforces location compatibility, role disjointness, and title alignment to prevent
    merging distinct roles that share corporate boilerplate text.
    """
    norm_snap_title = normalize_title(snapshot_title)
    doc1 = f"{norm_snap_title} {norm_snap_title} {' '.join(snapshot_description.split()[:200])}"

    best_cand = None
    best_sim = 0.0

    for cand in candidates:
        # Enforce location compatibility
        cand_loc = cand.get("location", "")
        if snapshot_location and cand_loc:
            if not are_locations_compatible(snapshot_location, cand_loc):
                continue

        cand_norm_title = normalize_title(cand.get("title", ""))

        # Check for mutually exclusive specializations (e.g. Frontend vs Backend)
        is_disjoint = False
        for w1, w2 in DISJOINT_ROLE_PAIRS:
            if (w1 in norm_snap_title and w2 in cand_norm_title) or (w2 in norm_snap_title and w1 in cand_norm_title):
                is_disjoint = True
                break
        if is_disjoint:
            continue

        # Prevent merging roles with low title overlap
        title_sim = fuzz.token_set_ratio(norm_snap_title, cand_norm_title)
        if title_sim < 65.0:
            continue

        cand_desc = cand.get("description_sample", "")
        doc2 = f"{cand_norm_title} {cand_norm_title} {cand_desc}"
        
        sim = compute_cosine_similarity(doc1, doc2)
        if sim >= threshold and sim > best_sim:
            best_sim = sim
            best_cand = cand

    if best_cand is not None:
        return SnapshotToCanonical(
            snapshot_id="",
            canonical_id=best_cand["id"],
            match_method=MatchMethod.SEMANTIC_EMBEDDING,
            confidence=round(best_sim, 3),
        )

    return None
