from datetime import datetime, timezone

from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class RemoteOKScraper(BaseScraper):
    source = JobSource.remoteok
    endpoint = "https://remoteok.com/api"

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        errors: list[str] = []
        jobs: list[JobRecord] = []

        try:
            response = await self.fetch(self.endpoint, headers={"Accept": "application/json"})
            data = response.json()
            for entry in data:
                if not isinstance(entry, dict) or "position" not in entry:
                    continue

                salary_text = _salary_text(entry)
                job = self.maybe_build_job(
                    {
                        "title": entry.get("position", "Unknown role"),
                        "company": entry.get("company", "Unknown company"),
                        "location": entry.get("location", "Remote"),
                        "description": entry.get("description", ""),
                        "description_html": entry.get("description", ""),
                        "job_url": entry.get("url") or "https://remoteok.com/",
                        "apply_url": entry.get("apply_url") or entry.get("url") or "https://remoteok.com/",
                        "job_type": entry.get("employment_type") or entry.get("job_type"),
                        "skills": entry.get("tags") or [],
                        "salary_text": salary_text,
                        "posted_at": datetime.fromtimestamp(entry.get("epoch", 0), tz=timezone.utc)
                        if entry.get("epoch")
                        else datetime.now(timezone.utc),
                        "source_job_id": entry.get("id"),
                        "source_website": "remoteok.com",
                    }
                )
                if job:
                    jobs.append(job)
        except Exception as exc:
            errors.append(f"RemoteOK fetch failed: {exc}")
            if settings.enable_demo_fallback_jobs:
                jobs.extend(_fallback_jobs(self))

        return jobs, errors


def _salary_text(entry: dict) -> str | None:
    salary_min = entry.get("salary_min")
    salary_max = entry.get("salary_max")
    currency = entry.get("salary_currency") or "USD"
    if salary_min and salary_max:
        return f"{currency} {salary_min} - {salary_max}"
    if salary_min:
        return f"{currency} {salary_min}"
    return None


def _fallback_jobs(scraper: RemoteOKScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Senior Python Engineer",
                "company": "Remote Stack",
                "location": "Remote",
                "description": "Build backend APIs and automation systems for distributed teams.",
                "job_url": "https://remoteok.com/remote-jobs/sample-python-engineer",
                "apply_url": "https://remoteok.com/remote-jobs/sample-python-engineer",
                "job_type": "full-time",
                "skills": ["python", "fastapi", "api"],
                "source_type": "demo",
                "source_website": "remoteok.com",
            }
        )
    ]
