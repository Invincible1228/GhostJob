"""Unit tests for ATS adapters with mocked payloads."""

import pytest
from ghostjob.adapters.greenhouse import GreenhouseAdapter
from ghostjob.adapters.lever import LeverAdapter
from ghostjob.adapters.ashby import AshbyAdapter
from ghostjob.core.models import ATSType, RawJob


def test_greenhouse_normalization():
    adapter = GreenhouseAdapter()
    raw_payload = {
        "id": 4892019,
        "title": "Senior Backend Engineer - Python",
        "location": {"name": "Bengaluru, India"},
        "departments": [{"name": "Platform Engineering"}],
        "content": "<p>We are seeking a <b>Senior Backend Engineer</b>.</p><br>Requirements: Python, AWS.",
        "absolute_url": "https://boards.greenhouse.io/zepto/jobs/4892019",
        "updated_at": "2026-02-15T10:00:00Z",
    }
    raw = RawJob(
        ats_type=ATSType.GREENHOUSE,
        ats_slug="zepto",
        external_id="4892019",
        payload=raw_payload,
    )
    posting = adapter.normalize("Zepto", raw)
    assert posting.title == "Senior Backend Engineer - Python"
    assert posting.location == "Bengaluru, India"
    assert posting.department == "Platform Engineering"
    assert "Requirements: Python, AWS." in posting.description_text
    assert posting.external_id == "4892019"
    assert len(posting.content_hash) == 64


def test_lever_normalization():
    adapter = LeverAdapter()
    raw_payload = {
        "id": "abc-123-xyz",
        "text": "Full Stack Engineer (React / Go)",
        "categories": {
            "location": "Bengaluru",
            "team": "Core Product",
            "commitment": "Full-time"
        },
        "descriptionPlain": "Build robust web applications with React and Go.",
        "lists": [
            {"text": "Requirements", "content": "3+ years Go experience"}
        ],
        "hostedUrl": "https://jobs.lever.co/cred/abc-123-xyz",
        "createdAt": 1708000000000,
    }
    raw = RawJob(
        ats_type=ATSType.LEVER,
        ats_slug="cred",
        external_id="abc-123-xyz",
        payload=raw_payload,
    )
    posting = adapter.normalize("CRED", raw)
    assert posting.title == "Full Stack Engineer (React / Go)"
    assert posting.location == "Bengaluru"
    assert posting.department == "Core Product"
    assert "Build robust web applications" in posting.description_text
    assert "3+ years Go experience" in posting.description_text


def test_ashby_normalization():
    adapter = AshbyAdapter()
    raw_payload = {
        "id": "ashby-456",
        "title": "Software Engineer II - Payments",
        "location": "Remote - India",
        "department": "Engineering",
        "employmentType": "FullTime",
        "descriptionPlain": "Work on scalable payment rails.",
        "jobUrl": "https://jobs.ashbyhq.com/ramp/ashby-456",
        "publishedAt": "2026-01-20T12:00:00Z"
    }
    raw = RawJob(
        ats_type=ATSType.ASHBY,
        ats_slug="ramp",
        external_id="ashby-456",
        payload=raw_payload,
    )
    posting = adapter.normalize("Ramp", raw)
    assert posting.title == "Software Engineer II - Payments"
    assert posting.location == "Remote - India"
    assert posting.department == "Engineering"
    assert "Work on scalable payment rails." in posting.description_text
