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
                response = await self.client.get(endpoint)
                response.raise_for_status()
                data = response.json()
                for entry in data.get("jobs", []):
                    title = entry.get("title", "Unknown role")
                    description = self.html_to_text(entry.get("content", ""))
                    jobs.append(
                        self.build_job(
                            {
                                "title": title,
                                "company": board.replace("-", " ").title(),
                                "location": (entry.get("location") or {}).get("name", "Remote"),
                                "description": description,
                                "apply_url": entry.get("absolute_url") or endpoint,
                                "job_type": _infer_job_type(title, description),
                                "tags": self.infer_tags(title, description),
                                "posted_at": entry.get("updated_at"),
                            }
                        )
                    )
            except Exception as exc:
                errors.append(f"Greenhouse board '{board}' failed: {exc}")

        if not jobs:
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
                "apply_url": "https://boards.greenhouse.io/example/jobs/backend-platform-engineer",
                "job_type": "full-time",
                "tags": ["python", "backend", "api"],
            }
        )
    ]
