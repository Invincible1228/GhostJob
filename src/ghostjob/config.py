"""Configuration settings for Ghost-Job Detector."""

from pathlib import Path
from pydantic import BaseModel, Field

# Base directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SEEDS_DIR = DATA_DIR / "seeds"
EXPORTS_DIR = DATA_DIR / "exports"
FIXTURES_DIR = DATA_DIR / "fixtures"

SEEDS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseModel):
    """Runtime application settings."""
    db_path: Path = DATA_DIR / "ghostjob.db"
    seed_file: Path = SEEDS_DIR / "companies.json"
    
    # Crawler settings
    request_timeout: float = 15.0
    max_concurrency: int = 5
    default_rate_limit_per_second: float = 2.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "GhostJobDetector/0.1 (+https://github.com/Invincible1228/ghost-job-detector; ethical research crawler)"
    )

    # Dedup settings
    fuzzy_title_threshold: float = 88.0
    semantic_similarity_threshold: float = 0.92

    # Scorer weights
    staleness_weight: float = 0.35
    repost_loop_weight: float = 0.30
    evergreen_weight: float = 0.15
    jd_quality_weight: float = 0.10
    location_clone_weight: float = 0.10


settings = Settings()
