"""Ashby public API adapter.

Public endpoint specification:
POST / GET https://api.ashbyhq.com/posting-api/job-board/{slug}
"""

import re
from datetime import datetime
import httpx

from ghostjob.adapters.base import ATSAdapter
from ghostjob.core.models import ATSType, JobPosting, RawJob


class AshbyAdapter(ATSAdapter):
    ats_type = ATSType.ASHBY

    SLUG_PATTERNS = [
        re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
    ]

    def detect(self, url_or_html: str) -> bool:
        return any(pat.search(url_or_html) for pat in self.SLUG_PATTERNS) or "ashbyhq.com" in url_or_html.lower()

    def extract_slug(self, url: str) -> str | None:
        for pat in self.SLUG_PATTERNS:
            match = pat.search(url)
            if match:
                return match.group(1).lower()
        return None

    async def fetch_jobs(self, slug: str, client: httpx.AsyncClient) -> list[RawJob]:
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
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
        location = item.get("location") or "Remote"
        dept = item.get("department") or ""
        employment_type = item.get("employmentType") or ""

        # Ashby provides descriptionPlain or descriptionHtml
        desc = item.get("descriptionPlain") or self.clean_html(item.get("descriptionHtml") or "")
        source_url = item.get("jobUrl") or f"https://jobs.ashbyhq.com/{raw.ats_slug}/{raw.external_id}"

        posted_dt = None
        published_at = item.get("publishedAt")
        if published_at:
            try:
                posted_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except Exception:
                posted_dt = None

        return JobPosting(
            company_name=company_name,
            ats_type=self.ats_type,
            ats_slug=raw.ats_slug,
            external_id=raw.external_id,
            title=title,
            location=str(location).strip(),
            department=str(dept).strip(),
            employment_type=str(employment_type).strip(),
            description_text=desc.strip(),
            source_url=source_url,
            posted_date_claimed=posted_dt,
        )
