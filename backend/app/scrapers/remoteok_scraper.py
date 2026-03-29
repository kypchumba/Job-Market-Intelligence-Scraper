from datetime import datetime, timezone

from .base import BaseScraper
from ..models import JobRecord, JobSource


class RemoteOKScraper(BaseScraper):
    source = JobSource.remoteok
    endpoint = "https://remoteok.com/api"

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        errors: list[str] = []
        jobs: list[JobRecord] = []

        try:
            response = await self.client.get(self.endpoint, headers={"Accept": "application/json"})
            response.raise_for_status()
            data = response.json()
            for entry in data:
                if not isinstance(entry, dict) or "position" not in entry:
                    continue
                jobs.append(
                    self.build_job(
                        {
                            "title": entry.get("position", "Unknown role"),
                            "company": entry.get("company", "Unknown company"),
                            "location": entry.get("location", "Remote"),
                            "description": entry.get("description", ""),
                            "apply_url": entry.get("url") or "https://remoteok.com/",
                            "job_type": "remote",
                            "tags": entry.get("tags") or [],
                            "salary_text": entry.get("salary_min"),
                            "posted_at": datetime.fromtimestamp(entry.get("epoch", 0), tz=timezone.utc)
                            if entry.get("epoch")
                            else datetime.now(timezone.utc),
                        }
                    )
                )
        except Exception as exc:
            errors.append(f"RemoteOK fetch failed: {exc}")
            jobs.extend(_fallback_jobs(self.source))

        return jobs, errors


def _fallback_jobs(source: JobSource) -> list[JobRecord]:
    samples = [
        {
            "title": "Senior Python Engineer",
            "company": "Remote Stack",
            "location": "Remote",
            "description": "Build backend APIs and automation systems for distributed teams.",
            "apply_url": "https://remoteok.com/remote-jobs/sample-python-engineer",
            "job_type": "full-time",
            "tags": ["python", "fastapi", "api"],
        },
        {
            "title": "Frontend React Developer",
            "company": "Async Studio",
            "location": "Remote - Europe/Africa",
            "description": "Own dashboards and data-rich user experiences for a hiring analytics platform.",
            "apply_url": "https://remoteok.com/remote-jobs/sample-react-developer",
            "job_type": "contract",
            "tags": ["react", "javascript", "analytics"],
        },
    ]
    scraper = object.__new__(RemoteOKScraper)
    scraper.source = source
    return [scraper.build_job(payload) for payload in samples]
