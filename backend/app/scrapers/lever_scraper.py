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
                response = await self.client.get(endpoint)
                response.raise_for_status()
                data = response.json()
                for entry in data:
                    categories = entry.get("categories") or {}
                    description = entry.get("descriptionPlain") or self.html_to_text(entry.get("description", ""))
                    jobs.append(
                        self.build_job(
                            {
                                "title": entry.get("text", "Unknown role"),
                                "company": company.replace("-", " ").title(),
                                "location": categories.get("location", "Remote"),
                                "description": description,
                                "apply_url": entry.get("hostedUrl") or endpoint,
                                "job_type": _normalize_commitment(categories.get("commitment")),
                                "tags": self.infer_tags(
                                    entry.get("text", ""),
                                    description,
                                    categories.get("team", ""),
                                ),
                                "posted_at": entry.get("createdAt"),
                                "salary_text": entry.get("salaryDescriptionPlain"),
                            }
                        )
                    )
            except Exception as exc:
                errors.append(f"Lever company '{company}' failed: {exc}")

        if not jobs:
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
                "apply_url": "https://jobs.lever.co/example/product-data-analyst",
                "job_type": "full-time",
                "tags": ["data", "analytics", "sql"],
            }
        )
    ]
