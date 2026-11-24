"""Normalization utilities for titles, locations, and text matching."""

import re

# Canonical Indian & Global city clusters
CITY_ALIASES: dict[str, str] = {
    "bangalore": "bengaluru",
    "bengaluru": "bengaluru",
    "blr": "bengaluru",
    "mumbai": "mumbai",
    "bombay": "mumbai",
    "delhi": "delhi_ncr",
    "new delhi": "delhi_ncr",
    "gurgaon": "delhi_ncr",
    "gurugram": "delhi_ncr",
    "noida": "delhi_ncr",
    "hyderabad": "hyderabad",
    "secunderabad": "hyderabad",
    "chennai": "chennai",
    "madras": "chennai",
    "pune": "pune",
    "kolkata": "kolkata",
    "calcutta": "kolkata",
    "san francisco": "sf_bay_area",
    "sf": "sf_bay_area",
    "remote": "remote",
    "anywhere": "remote",
    "work from home": "remote",
}


def normalize_title(title: str) -> str:
    """Normalize job title by removing noisy hiring tags and standardizing punctuation."""
    if not title:
        return ""
    t = title.lower()
    # Strip common recruitment hype badges in parentheses or brackets
    noise_patterns = [
        r"[\(\[]\s*immediate joiner\s*[\)\]]",
        r"[\(\[]\s*urgently hiring\s*[\)\]]",
        r"[\(\[]\s*urgent hiring\s*[\)\]]",
        r"[\(\[]\s*m/f/d\s*[\)\]]",
        r"[\(\[]\s*f/m/d\s*[\)\]]",
        r"[\(\[]\s*w/m/d\s*[\)\]]",
        r"[\(\[]\s*remote\s*[\)\]]",
        r"[\(\[]\s*hybrid\s*[\)\]]",
        r"-\s*remote\b",
        r"\|\s*remote\b",
    ]
    for pat in noise_patterns:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)

    # Standardize common acronyms
    t = re.sub(r"\bsde\s*[-_]?\s*1\b", "software development engineer i", t)
    t = re.sub(r"\bsde\s*[-_]?\s*2\b", "software development engineer ii", t)
    t = re.sub(r"\bsde\s*[-_]?\s*3\b", "software development engineer iii", t)
    t = re.sub(r"\bsr\.?\b", "senior", t)
    t = re.sub(r"\bjr\.?\b", "junior", t)
    t = re.sub(r"\bml\b", "machine learning", t)
    t = re.sub(r"\bai\b", "artificial intelligence", t)

    # Remove non-alphanumeric except spaces
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(t.split())


def normalize_location(location: str) -> str:
    """Canonicalize city or state to normalized regional buckets."""
    if not location:
        return "remote"
    loc = location.lower()
    
    # Check for remote markers first
    if any(m in loc for m in ["remote", "wfh", "anywhere", "telecommute", "distributed"]):
        return "remote"

    for alias, canonical in CITY_ALIASES.items():
        if re.search(rf"\b{alias}\b", loc):
            return canonical

    # If no alias match, return cleaned string
    clean = re.sub(r"[^a-z0-9\s]", " ", loc)
    return " ".join(clean.split())


def are_locations_compatible(loc1: str, loc2: str) -> bool:
    """Check if two job locations are compatible for deduplication matching."""
    norm1 = normalize_location(loc1)
    norm2 = normalize_location(loc2)
    
    # If either is remote or both are in the same canonical city
    if norm1 == "remote" or norm2 == "remote" or norm1 == norm2:
        return True
    return False
