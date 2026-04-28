from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class LeverScraper(BaseScraper):
    source = JobSource.lever

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for company in settings.lever_companies:
            endpoint = f"https://api.lever.co/v0/postings/{company}?mode=json"
            try:
                response = await self.fetch(endpoint, headers={"Accept": "application/json"})
                data = response.json()
                for entry in data:
                    categories = entry.get("categories") or {}
                    description_html = entry.get("description") or ""
                    description = entry.get("descriptionPlain") or self.html_to_text(description_html)
                    job = self.maybe_build_job(
                        {
                            "title": entry.get("text", "Unknown role"),
                            "company": company.replace("-", " ").title(),
                            "location": categories.get("location", "Remote"),
                            "description": description,
                            "description_html": description_html,
                            "job_url": entry.get("hostedUrl") or endpoint,
                            "apply_url": entry.get("applyUrl") or entry.get("hostedUrl") or endpoint,
                            "job_type": _normalize_commitment(categories.get("commitment")),
                            "skills": self.infer_tags(
                                entry.get("text", ""),
                                description,
                                categories.get("team", ""),
                            ),
                            "posted_at": entry.get("createdAt"),
                            "salary_text": entry.get("salaryDescriptionPlain"),
                            "source_job_id": entry.get("id"),
                            "source_website": "jobs.lever.co",
                        }
                    )
                    if job:
                        jobs.append(job)
            except Exception as exc:
                errors.append(f"Lever company '{company}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return jobs, errors


def _normalize_commitment(value: str | None) -> str:
    return (value or "unknown").strip().lower()


def _fallback_jobs(scraper: LeverScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Product Data Analyst",
                "company": "Example Lever",
                "location": "Remote",
                "description": "Analyze hiring funnel and product signals for recruiting operations.",
                "job_url": "https://jobs.lever.co/example/product-data-analyst",
                "apply_url": "https://jobs.lever.co/example/product-data-analyst",
                "job_type": "full-time",
                "skills": ["data", "analytics", "sql"],
                "source_type": "demo",
                "source_website": "jobs.lever.co",
            }
        )
    ]
