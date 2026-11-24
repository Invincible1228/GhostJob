"""Asynchronous crawler engine with rate-limiting, retries, and snapshot persistence."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ghostjob.adapters import get_adapter
from ghostjob.config import settings
from ghostjob.core.models import Company, JobPosting, JobSnapshot, ATSType
from ghostjob.db.repository import Repository

logger = logging.getLogger(__name__)


class CrawlerEngine:
    """Robust, ethical async crawler directly ingesting from official ATS endpoints."""

    def __init__(self, repo: Repository, concurrency: int = 5):
        self.repo = repo
        self.semaphore = asyncio.Semaphore(concurrency)
        self.headers = {
            "User-Agent": settings.user_agent,
            "Accept": "application/json, text/plain, */*",
        }

    async def crawl_company(
        self,
        company: Company,
        client: httpx.AsyncClient,
    ) -> list[JobPosting]:
        """Crawl a single company's ATS endpoint, append snapshots, and update metadata."""
        adapter = get_adapter(company.ats_type)
        if not adapter:
            logger.warning(f"No adapter available for ATS {company.ats_type} ({company.name})")
            return []

        async with self.semaphore:
            # Politeness delay between company fetches
            await asyncio.sleep(0.4)
            try:
                raw_jobs = await adapter.fetch_jobs(company.ats_slug, client)
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP {e.response.status_code} fetching {company.name} ({company.ats_slug}): {e}")
                return []
            except Exception as e:
                logger.error(f"Failed to fetch {company.name}: {e}")
                return []

        postings: list[JobPosting] = []
        now = datetime.utcnow()

        # Update company last seen
        company_id = self.repo.upsert_company(company)

        for raw in raw_jobs:
            try:
                posting = adapter.normalize(company.name, raw)
                postings.append(posting)

                # Append-only snapshot write
                snapshot = JobSnapshot(
                    company_id=company_id,
                    company_name=company.name,
                    source_url=posting.source_url,
                    external_id=posting.external_id,
                    scraped_at=now,
                    title=posting.title,
                    location=posting.location,
                    dept=posting.department,
                    description_text=posting.description_text,
                    content_hash=posting.content_hash,
                    posted_date_claimed=posting.posted_date_claimed,
                    raw_json=json.dumps(raw.payload),
                )
                self.repo.insert_snapshot(snapshot)
            except Exception as e:
                logger.debug(f"Normalization error for job in {company.name}: {e}")
                continue

        return postings

    async def run(
        self,
        companies: list[Company],
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Run crawl over target companies concurrently with progress reporting."""
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        async with httpx.AsyncClient(headers=self.headers, limits=limits, timeout=settings.request_timeout) as client:
            tasks = [self.crawl_company(comp, client) for comp in companies]
            
            results = []
            for coro in asyncio.as_completed(tasks):
                res = await coro
                results.append(res)
                if progress_callback:
                    progress_callback(len(res))

        total_scraped = sum(len(r) for r in results)
        successful_companies = sum(1 for r in results if len(r) > 0)

        return {
            "companies_crawled": len(companies),
            "successful_companies": successful_companies,
            "total_jobs_scraped": total_scraped,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
