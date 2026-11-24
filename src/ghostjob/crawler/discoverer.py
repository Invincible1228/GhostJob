"""Career Page & ATS signature discoverer.

Discovers ATS vendor and slug from company career URLs or landing pages.
"""

import re
from urllib.parse import urljoin
import httpx

from ghostjob.adapters import ADAPTER_REGISTRY
from ghostjob.core.models import ATSType


class CareerDiscoverer:
    """Detects ATS type and tenant slug for companies."""

    CAREERS_PATHS = [
        "/careers",
        "/jobs",
        "/join-us",
        "/about/careers",
        "/work-with-us",
    ]

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    WORKDAY_PATTERN = re.compile(r"([a-zA-Z0-9_\-]+)\.(?:wd\d+\.)?myworkdayjobs\.com", re.IGNORECASE)
    SMARTRECRUITERS_PATTERN = re.compile(r"smartrecruiters\.com/([a-zA-Z0-9_\-]+)", re.IGNORECASE)
    BAMBOOHR_PATTERN = re.compile(r"([a-zA-Z0-9_\-]+)\.bamboohr\.com/careers", re.IGNORECASE)

    def detect_from_url(self, url: str) -> tuple[ATSType, str] | None:
        """Attempt to match URL directly against known ATS patterns."""
        for ats_type, adapter in ADAPTER_REGISTRY.items():
            if adapter.detect(url):
                slug = adapter.extract_slug(url)
                if slug:
                    return ats_type, slug

        # Extended ATS vendors (detection & queueing)
        wd_match = self.WORKDAY_PATTERN.search(url)
        if wd_match:
            return ATSType.WORKDAY, wd_match.group(1).lower()

        sr_match = self.SMARTRECRUITERS_PATTERN.search(url)
        if sr_match:
            return ATSType.SMARTRECRUITERS, sr_match.group(1).lower()

        bhr_match = self.BAMBOOHR_PATTERN.search(url)
        if bhr_match:
            return ATSType.BAMBOOHR, bhr_match.group(1).lower()

        return None

    def detect_from_html(self, html: str) -> tuple[ATSType, str] | None:
        """Scan HTML content for embedded ATS iframe, links, or widget references."""
        for ats_type, adapter in ADAPTER_REGISTRY.items():
            for pat in getattr(adapter, "SLUG_PATTERNS", []):
                match = pat.search(html)
                if match:
                    return ats_type, match.group(1).lower()

        wd_match = self.WORKDAY_PATTERN.search(html)
        if wd_match:
            return ATSType.WORKDAY, wd_match.group(1).lower()

        sr_match = self.SMARTRECRUITERS_PATTERN.search(html)
        if sr_match:
            return ATSType.SMARTRECRUITERS, sr_match.group(1).lower()

        bhr_match = self.BAMBOOHR_PATTERN.search(html)
        if bhr_match:
            return ATSType.BAMBOOHR, bhr_match.group(1).lower()

        return None

    async def discover(self, domain: str, client: httpx.AsyncClient) -> tuple[ATSType, str, str] | None:
        """
        Probe domain career paths and detect ATS endpoint.
        Returns (ats_type, slug, careers_url) or None.
        """
        base_url = f"https://{domain.strip('/')}"
        
        for path in self.CAREERS_PATHS:
            target_url = urljoin(base_url, path)
            try:
                resp = await client.get(target_url, follow_redirects=True, timeout=10.0)
                # 1. Check final redirected URL
                match = self.detect_from_url(str(resp.url))
                if match:
                    return match[0], match[1], str(resp.url)

                # 2. Check page HTML for embedded ATS links/frames
                html_match = self.detect_from_html(resp.text)
                if html_match:
                    return html_match[0], html_match[1], str(resp.url)
            except Exception:
                continue

        return None
