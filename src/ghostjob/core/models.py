"""Domain models and schemas for Ghost-Job Detector."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import hashlib
from pydantic import BaseModel, Field


class ATSType(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    SMARTRECRUITERS = "smartrecruiters"
    BAMBOOHR = "bamboohr"
    CUSTOM = "custom"


class CanonicalStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    ZOMBIE = "zombie"


class GhostLabel(str, Enum):
    ACTIVE = "active"          # Low risk, normal healthy job posting
    AGING = "aging"            # Moderate risk, open longer than expected
    LIKELY_GHOST = "likely_ghost"  # High risk, repost loops / evergreen signals
    ZOMBIE = "zombie"          # Extreme risk, persistent open role with stagnant activity


class Company(BaseModel):
    """Target company profile."""
    id: str | None = None
    name: str
    domain: str
    ats_type: ATSType
    ats_slug: str
    careers_url: str | None = None
    employee_count: int | None = None
    last_seen_at: datetime | None = None


class RawJob(BaseModel):
    """Raw payload scraped directly from ATS endpoint."""
    ats_type: ATSType
    ats_slug: str
    external_id: str
    payload: dict[str, Any]


class JobPosting(BaseModel):
    """Normalized job posting structure across any ATS source."""
    company_name: str
    ats_type: ATSType
    ats_slug: str
    external_id: str
    title: str
    location: str
    department: str = ""
    employment_type: str = ""
    description_text: str
    source_url: str
    posted_date_claimed: datetime | None = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def content_hash(self) -> str:
        """Deterministic SHA-256 fingerprint of the normalized content."""
        norm_title = " ".join(self.title.lower().split())
        norm_loc = " ".join(self.location.lower().split())
        # First 400 words of description are enough to identify the job body without dynamic tracking tags
        norm_desc_words = " ".join(self.description_text.lower().split()[:400])
        raw_sig = f"{norm_title}|{norm_loc}|{norm_desc_words}"
        return hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()


class JobSnapshot(BaseModel):
    """Append-only snapshot record stored in DB."""
    id: str | None = None
    company_id: str
    company_name: str
    source_url: str
    external_id: str
    scraped_at: datetime
    title: str
    location: str
    dept: str = ""
    description_text: str
    content_hash: str
    posted_date_claimed: datetime | None = None
    raw_json: str | None = None


class CanonicalJob(BaseModel):
    """Consolidated unique role tracked over time across snapshots."""
    id: str
    company_id: str
    company_name: str
    title: str
    location: str
    department: str = ""
    description_sample: str = ""
    first_seen_at: datetime
    last_seen_at: datetime
    times_seen: int = 1
    times_reposted: int = 0
    clone_count: int = 1
    status: CanonicalStatus = CanonicalStatus.OPEN
    content_hash: str = ""
    active_snapshot_id: str | None = None


class MatchMethod(str, Enum):
    EXACT_ID = "exact_id"
    EXACT_HASH = "exact_hash"
    FUZZY_RULES = "fuzzy_rules"
    SEMANTIC_EMBEDDING = "semantic_embedding"


class SnapshotToCanonical(BaseModel):
    snapshot_id: str
    canonical_id: str
    match_method: MatchMethod
    confidence: float


class GhostScore(BaseModel):
    """Ghost probability calculation with explainability."""
    canonical_id: str
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: float = Field(ge=0.0, le=1.0)
    label: GhostLabel
    reasons: list[str] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)
