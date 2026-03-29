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
    max_jobs_per_source: int = 25
    scrape_rate_limit_requests: int = 3
    scrape_rate_limit_window_seconds: int = 60
    scrape_cooldown_seconds: int = 45
    scrape_api_keys: list[str] = ["local-dev-scrape-key"]
    greenhouse_boards: list[str] = ["stripe", "airtable"]
    lever_companies: list[str] = ["netlify", "sourcegraph"]
    ashby_boards: list[str] = ["notion"]
    careers_pages: list[str] = [
        "https://automattic.com/work-with-us/",
        "https://careers.mozilla.org/listings/",
    ]
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(env_prefix="JOBINTEL_", env_file=".env", extra="ignore")


settings = Settings()
