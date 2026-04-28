from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class GreenhouseScraper(BaseScraper):
    source = JobSource.greenhouse

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for board in settings.greenhouse_boards:
            endpoint = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
            try:
                response = await self.fetch(endpoint, headers={"Accept": "application/json"})
                data = response.json()
                for entry in data.get("jobs", []):
                    title = entry.get("title", "Unknown role")
                    description_html = entry.get("content", "")
                    description = self.html_to_text(description_html)
                    job = self.maybe_build_job(
                        {
                            "title": title,
                            "company": board.replace("-", " ").title(),
                            "location": (entry.get("location") or {}).get("name", "Remote"),
                            "description": description,
                            "description_html": description_html,
                            "job_url": entry.get("absolute_url") or endpoint,
                            "apply_url": entry.get("absolute_url") or endpoint,
                            "job_type": _infer_job_type(title, description),
                            "skills": self.infer_tags(title, description),
                            "posted_at": entry.get("updated_at") or entry.get("first_published"),
                            "source_job_id": entry.get("id"),
                            "source_website": "boards.greenhouse.io",
                        }
                    )
                    if job:
                        jobs.append(job)
            except Exception as exc:
                errors.append(f"Greenhouse board '{board}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return jobs, errors


def _infer_job_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    for label in ["full-time", "contract", "internship", "part-time"]:
        if label in text:
            return label
    return "unknown"


def _fallback_jobs(scraper: GreenhouseScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Backend Platform Engineer",
                "company": "Example Greenhouse",
                "location": "Remote",
                "description": "Build internal services, APIs, and automation for a scaling engineering team.",
                "job_url": "https://boards.greenhouse.io/example/jobs/backend-platform-engineer",
                "apply_url": "https://boards.greenhouse.io/example/jobs/backend-platform-engineer",
                "job_type": "full-time",
                "skills": ["python", "backend", "api"],
                "source_type": "demo",
                "source_website": "boards.greenhouse.io",
            }
        )
    ]
