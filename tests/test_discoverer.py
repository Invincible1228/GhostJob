"""Tests for career page discoverer and ATS regex signatures."""

from ghostjob.crawler.discoverer import CareerDiscoverer
from ghostjob.core.models import ATSType


def test_discoverer_url_matching():
    disc = CareerDiscoverer()
    
    # Greenhouse
    res = disc.detect_from_url("https://boards.greenhouse.io/postman/jobs/12345")
    assert res is not None
    assert res[0] == ATSType.GREENHOUSE
    assert res[1] == "postman"

    # Lever
    res = disc.detect_from_url("https://jobs.lever.co/meesho")
    assert res is not None
    assert res[0] == ATSType.LEVER
    assert res[1] == "meesho"

    # Ashby
    res = disc.detect_from_url("https://jobs.ashbyhq.com/ramp")
    assert res is not None
    assert res[0] == ATSType.ASHBY
    assert res[1] == "ramp"

    # Workday
    res = disc.detect_from_url("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite")
    assert res is not None
    assert res[0] == ATSType.WORKDAY
    assert res[1] == "nvidia"

    # SmartRecruiters
    res = disc.detect_from_url("https://careers.smartrecruiters.com/AcmeCorp/12345")
    assert res is not None
    assert res[0] == ATSType.SMARTRECRUITERS
    assert res[1] == "acmecorp"


def test_discoverer_html_matching():
    disc = CareerDiscoverer()
    sample_html = """
    <html>
      <head><title>Careers at Acme</title></head>
      <body>
        <h1>Join Our Team</h1>
        <iframe src="https://boards.greenhouse.io/embed/job_board?for=acmeco"></iframe>
      </body>
    </html>
    """
    res = disc.detect_from_html(sample_html)
    assert res is not None
    assert res[0] == ATSType.GREENHOUSE
    assert res[1] == "acmeco"
