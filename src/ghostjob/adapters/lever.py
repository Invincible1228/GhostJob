"""Lever public API adapter.

Public endpoint specification:
https://api.lever.co/v0/postings/{slug}?mode=json
"""

import re
from datetime import datetime, timezone
import httpx

from ghostjob.adapters.base import ATSAdapter
from ghostjob.core.models import ATSType, JobPosting, RawJob


class LeverAdapter(ATSAdapter):
    ats_type = ATSType.LEVER

    SLUG_PATTERNS = [
        re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"api\.lever\.co/v0/postings/([a-zA-Z0-9_\-]+)", re.IGNORECASE),
    ]

    def detect(self, url_or_html: str) -> bool:
        return any(pat.search(url_or_html) for pat in self.SLUG_PATTERNS) or "lever.co" in url_or_html.lower()

    def extract_slug(self, url: str) -> str | None:
        for pat in self.SLUG_PATTERNS:
            match = pat.search(url)
            if match:
                return match.group(1).lower()
        return None

    async def fetch_jobs(self, slug: str, client: httpx.AsyncClient) -> list[RawJob]:
        api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        response = await client.get(api_url, timeout=20.0)
        response.raise_for_status()
        jobs_data = response.json()

        results: list[RawJob] = []
        if isinstance(jobs_data, list):
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
        text_title = (item.get("text") or "Untitled Position").strip()

        # Categories
        cats = item.get("categories") or {}
        location = cats.get("location") or "Remote"
        dept = cats.get("department") or cats.get("team") or ""
        commitment = cats.get("commitment") or ""

        # Description text
        desc_plain = item.get("descriptionPlain") or ""
        if not desc_plain:
            desc_plain = self.clean_html(item.get("description", ""))

        # Additional lists in Lever payload (Requirements, Responsibilities)
        lists = item.get("lists") or []
        extra_parts = []
        for lst in lists:
            header = lst.get("text", "")
            content = self.clean_html(lst.get("content", ""))
            if header or content:
                extra_parts.append(f"{header}\n{content}".strip())
        
        full_desc = desc_plain + ("\n\n" + "\n\n".join(extra_parts) if extra_parts else "")

        source_url = item.get("hostedUrl") or f"https://jobs.lever.co/{raw.ats_slug}/{raw.external_id}"

        # Created date
        created_at_ts = item.get("createdAt")
        posted_dt = None
        if created_at_ts:
            try:
                # Milliseconds timestamp
                posted_dt = datetime.fromtimestamp(created_at_ts / 1000.0, tz=timezone.utc)
            except Exception:
                posted_dt = None

        return JobPosting(
            company_name=company_name,
            ats_type=self.ats_type,
            ats_slug=raw.ats_slug,
            external_id=raw.external_id,
            title=text_title,
            location=location.strip(),
            department=dept.strip(),
            employment_type=commitment.strip(),
            description_text=full_desc.strip(),
            source_url=source_url,
            posted_date_claimed=posted_dt,
        )
