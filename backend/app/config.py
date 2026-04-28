from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent


class Settings(BaseSettings):
    app_name: str = "Job Market Intelligence Scraper"
    app_version: str = "0.1.0"
    data_file: Path = BASE_DIR / "data" / "jobs.json"
    request_timeout_seconds: float = 20.0
    scrape_timeout_seconds: float = 30.0
    scraper_concurrency: int = 4
    detail_request_concurrency: int = 6
    max_jobs_per_source: int = 25
    max_pages_per_source: int = 3
    max_detail_jobs_per_source: int = 40
    scrape_rate_limit_requests: int = 3
    scrape_rate_limit_window_seconds: int = 60
    scrape_cooldown_seconds: int = 45
    request_max_retries: int = 3
    request_backoff_seconds: float = 1.25
    request_min_delay_seconds: float = 0.5
    request_jitter_seconds: float = 0.35
    request_retry_statuses: list[int] = [429, 500, 502, 503, 504]
    enable_demo_fallback_jobs: bool = False
    scrape_api_keys: list[str] = ["local-dev-scrape-key"]
    scrape_user_agents: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    ]
    greenhouse_boards: list[str] = ["stripe", "airtable"]
    lever_companies: list[str] = ["netlify", "sourcegraph"]
    ashby_boards: list[str] = ["notion"]
    careers_pages: list[str] = [
        "https://automattic.com/work-with-us/",
        "https://careers.mozilla.org/listings/",
        "https://www.safaricom.co.ke/about/careers",
        "https://careers.oldmutual.com/",
    ]
    ngo_pages: list[str] = [
        "https://www.amref.org/work-with-us/",
        "https://www.brac.net/jobs/",
        "https://www.care.org/careers/",
    ]
    myjobmag_pages: list[str] = [
        "https://www.myjobmag.co.ke/jobs/",
        "https://www.myjobmag.com/jobs/",
    ]
    brightermonday_pages: list[str] = [
        "https://www.brightermonday.co.ke/jobs",
    ]
    corporatestaffing_pages: list[str] = [
        "https://www.corporatestaffing.co.ke/jobs/",
    ]
    fuzu_pages: list[str] = [
        "https://www.fuzu.com/job",
    ]
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_prefix="JOBINTEL_", env_file=".env", extra="ignore")


settings = Settings()
