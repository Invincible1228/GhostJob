"""Greenhouse public API adapter.

Public endpoint specification:
https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
"""

import re
from datetime import datetime
from typing import Any
import httpx

from ghostjob.adapters.base import ATSAdapter
from ghostjob.core.models import ATSType, JobPosting, RawJob


class GreenhouseAdapter(ATSAdapter):
    ats_type = ATSType.GREENHOUSE

    SLUG_PATTERNS = [
        re.compile(r"boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"job-boards\.greenhouse\.io/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
    ]

    def detect(self, url_or_html: str) -> bool:
        return any(pat.search(url_or_html) for pat in self.SLUG_PATTERNS) or "greenhouse.io" in url_or_html.lower()

    def extract_slug(self, url: str) -> str | None:
        for pat in self.SLUG_PATTERNS:
            match = pat.search(url)
            if match:
                return match.group(1).lower()
        return None

    async def fetch_jobs(self, slug: str, client: httpx.AsyncClient) -> list[RawJob]:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        response = await client.get(api_url, timeout=20.0)
        response.raise_for_status()
        data = response.json()
        jobs_data = data.get("jobs", [])

        results: list[RawJob] = []
        for item in jobs_data:
            ext_id = str(item.get("id"))
            results.append(
                RawJob(
                    ats_type=self.ats_type,
                    ats_slug=slug,
                    external_id=ext_id,
                    payload=item,
                )
            )
        return results

    def normalize(self, company_name: str, raw: RawJob) -> JobPosting:
        item = raw.payload
        title = (item.get("title") or "Untitled Position").strip()

        # Location extraction
        loc_data = item.get("location")
        if isinstance(loc_data, dict):
            location = loc_data.get("name") or "Remote"
        elif isinstance(loc_data, str):
            location = loc_data
        else:
            location = "Remote"

        # Department / Teams
        departments = item.get("departments", [])
        dept = departments[0].get("name", "") if departments else ""

        # Content / Description
        content_html = item.get("content") or ""
        clean_desc = self.clean_html(content_html)

        # Source URL
        source_url = item.get("absolute_url") or f"https://boards.greenhouse.io/{raw.ats_slug}/jobs/{raw.external_id}"

        # Posted date claimed
        updated_at_str = item.get("updated_at")
        posted_dt = None
        if updated_at_str:
            try:
                posted_dt = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            except Exception:
                posted_dt = None

        return JobPosting(
            company_name=company_name,
            ats_type=self.ats_type,
            ats_slug=raw.ats_slug,
            external_id=raw.external_id,
            title=title,
            location=location.strip(),
            department=dept.strip(),
            description_text=clean_desc,
            source_url=source_url,
            posted_date_claimed=posted_dt,
        )
