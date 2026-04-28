from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class AshbyScraper(BaseScraper):
    source = JobSource.ashby

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for board in settings.ashby_boards:
            endpoint = f"https://jobs.ashbyhq.com/api/non-user-graphql?op=apiJobBoardWithTeams&organizationHostedJobsPageName={board}"
            try:
                response = await self.fetch(endpoint, headers={"Accept": "application/json"})
                data = response.json()
                board_data = data.get("data", {}).get("jobBoard") or {}
                company = board_data.get("name") or board.replace("-", " ").title()
                for team in board_data.get("jobPostingsByTeam", []):
                    for entry in team.get("jobPostings", []):
                        description_html = entry.get("descriptionHtml", "")
                        description = self.html_to_text(description_html)
                        location_parts = entry.get("locationName") or entry.get("secondaryLocations") or []
                        job = self.maybe_build_job(
                            {
                                "title": entry.get("title", "Unknown role"),
                                "company": company,
                                "location": _location_text(location_parts),
                                "description": description,
                                "description_html": description_html,
                                "job_url": entry.get("jobUrl") or endpoint,
                                "apply_url": entry.get("jobUrl") or endpoint,
                                "job_type": (entry.get("employmentType") or "unknown").lower(),
                                "skills": self.infer_tags(entry.get("title", ""), description, team.get("name", "")),
                                "posted_at": entry.get("publishedDate"),
                                "source_job_id": entry.get("id"),
                                "source_website": "jobs.ashbyhq.com",
                            }
                        )
                        if job:
                            jobs.append(job)
            except Exception as exc:
                errors.append(f"Ashby board '{board}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return jobs, errors


def _location_text(value) -> str:
    if isinstance(value, str):
        return value or "Remote"
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return first.get("locationName", "Remote")
        return str(first)
    return "Remote"


def _fallback_jobs(scraper: AshbyScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Senior Frontend Engineer",
                "company": "Example Ashby",
                "location": "Remote",
                "description": "Ship polished product experiences and improve frontend architecture.",
                "job_url": "https://jobs.ashbyhq.com/example/senior-frontend-engineer",
                "apply_url": "https://jobs.ashbyhq.com/example/senior-frontend-engineer",
                "job_type": "full-time",
                "skills": ["react", "typescript", "frontend"],
                "source_type": "demo",
                "source_website": "jobs.ashbyhq.com",
            }
        )
    ]
