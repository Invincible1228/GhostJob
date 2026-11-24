"""Abstract base protocol and interface for ATS adapters."""

import re
from abc import ABC, abstractmethod
from typing import Any
import httpx

from ghostjob.core.models import ATSType, JobPosting, RawJob


class ATSAdapter(ABC):
    """Abstract interface for all ATS scraping adapters."""

    ats_type: ATSType

    @abstractmethod
    def detect(self, url_or_html: str) -> bool:
        """Return True if this adapter handles the target URL or HTML signature."""
        ...

    @abstractmethod
    def extract_slug(self, url: str) -> str | None:
        """Extract the ATS organization slug from a career URL."""
        ...

    @abstractmethod
    async def fetch_jobs(self, slug: str, client: httpx.AsyncClient) -> list[RawJob]:
        """Fetch raw listings from the ATS public endpoint."""
        ...

    @abstractmethod
    def normalize(self, company_name: str, raw: RawJob) -> JobPosting:
        """Convert an ATS-specific raw payload into a standard JobPosting."""
        ...

    @staticmethod
    def clean_html(html_text: str | None) -> str:
        """Strip HTML tags and normalize whitespace."""
        if not html_text:
            return ""
        # Remove script and style elements
        text = re.sub(r"<(script|style).*?>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
        # Replace breaks/paragraphs with newlines
        text = re.sub(r"<(br|p|div|li)[^>]*>", "\n", text, flags=re.IGNORECASE)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Unescape common HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        # Collapse excessive whitespace while preserving single newlines
        lines = [" ".join(line.split()) for line in text.split("\n")]
        return "\n".join(line for line in lines if line)
