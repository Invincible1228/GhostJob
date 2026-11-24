"""Lightweight REST API service providing search, filters, and job explainability."""

import json
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ghostjob.config import settings
from ghostjob.db.repository import Repository

repo = Repository(settings.db_path)
TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"

app = FastAPI(
    title="Ghost-Job Detector API & Dashboard",
    description="Direct-ATS Ingestion & Explainable Ghost Job Probability API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the interactive web dashboard."""
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Ghost-Job Detector API</h1><p>Visit <a href='/docs'>/docs</a> for Swagger UI.</p>"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/stats")
def get_stats() -> dict[str, Any]:
    """Return high-level metrics and distribution."""
    return repo.get_metrics_summary()


@app.get("/api/companies")
def list_companies() -> list[dict[str, Any]]:
    """Return target companies registered in the directory."""
    return repo.get_companies()


@app.get("/api/jobs")
def list_jobs(
    company: str | None = None,
    city: str | None = None,
    label: str | None = None,
    min_ghost_score: float | None = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Query jobs with ghost probability and filter options."""
    all_jobs = repo.get_all_canonical_jobs()

    filtered = []
    for j in all_jobs:
        if company and company.lower() not in j["company_name"].lower():
            continue
        if city and city.lower() not in j["location"].lower():
            continue
        if label and (j.get("latest_ghost_label") or "").lower() != label.lower():
            continue
        if min_ghost_score is not None:
            score = j.get("latest_ghost_score") or 0.0
            if score < min_ghost_score:
                continue

        # Parse reasons
        reasons = []
        if j.get("reasons_json"):
            try:
                reasons = json.loads(j["reasons_json"])
            except Exception:
                reasons = []

        filtered.append({
            "id": j["id"],
            "company_name": j["company_name"],
            "company_domain": j["company_domain"],
            "title": j["title"],
            "location": j["location"],
            "department": j.get("dept", ""),
            "status": j["status"],
            "first_seen_at": j["first_seen_at"],
            "last_seen_at": j["last_seen_at"],
            "times_seen": j["times_seen"],
            "times_reposted": j["times_reposted"],
            "ghost_score": j.get("latest_ghost_score") or 0.0,
            "ghost_label": j.get("latest_ghost_label") or "active",
            "top_reasons": reasons[:2],
        })

    paginated = filtered[offset: offset + limit]
    return {
        "total": len(filtered),
        "limit": limit,
        "offset": offset,
        "jobs": paginated,
    }


@app.get("/api/jobs/{canonical_id}/explain")
def explain_job(canonical_id: str) -> dict[str, Any]:
    """Detailed explanation of why a job is marked as ghost or active."""
    job = repo.get_canonical_job_by_id(canonical_id)
    if not job:
        raise HTTPException(status_code=404, detail="Canonical job posting not found")

    reasons = []
    signals = {}
    caveats = []

    if job.get("reasons_json"):
        try:
            reasons = json.loads(job["reasons_json"])
        except Exception:
            reasons = []
    if job.get("signals_json"):
        try:
            signals = json.loads(job["signals_json"])
        except Exception:
            signals = {}
    if job.get("caveats_json"):
        try:
            caveats = json.loads(job["caveats_json"])
        except Exception:
            caveats = []

    return {
        "id": job["id"],
        "company_name": job["company_name"],
        "title": job["title"],
        "location": job["location"],
        "status": job["status"],
        "ghost_score": job.get("latest_ghost_score") or 0.0,
        "ghost_label": job.get("latest_ghost_label") or "active",
        "reasons": reasons,
        "signals": signals,
        "caveats": caveats,
        "history": {
            "first_seen_at": job["first_seen_at"],
            "last_seen_at": job["last_seen_at"],
            "times_seen": job["times_seen"],
            "times_reposted": job["times_reposted"],
        }
    }
