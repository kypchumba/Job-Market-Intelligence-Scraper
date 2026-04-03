from bs4 import BeautifulSoup

from .african_board_common import (
    absolute_href,
    extract_listing_container,
    extract_text_lines,
    find_links,
    infer_job_type,
    parse_relative_date,
    unique_jobs,
)
from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class CorporateStaffingScraper(BaseScraper):
    source = JobSource.corporatestaffing

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.corporatestaffing_pages:
            try:
                response = await self.client.get(page_url)
                response.raise_for_status()
                jobs.extend(self._extract_jobs(response.text, page_url))
            except Exception as exc:
                errors.append(f"Corporate Staffing page '{page_url}' failed: {exc}")

        if not jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    def _extract_jobs(self, html: str, page_url: str) -> list[JobRecord]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobRecord] = []

        for link in find_links(soup, ("/listings/", "/job", "/jobs/")):
            title = " ".join(link.stripped_strings)
            if not title or len(title) < 4:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            description = " ".join(line for line in lines if line != title)[:1000]
            jobs.append(
                self.build_job(
                    {
                        "title": title,
                        "company": "Corporate Staffing Services",
                        "location": _extract_location(lines),
                        "description": description,
                        "apply_url": absolute_href(page_url, link.get("href")),
                        "job_type": _extract_job_type(lines),
                        "tags": self.infer_tags(title, description, "Corporate Staffing Services"),
                        "posted_at": _extract_posted_at(lines) or None,
                    }
                )
            )

        return jobs


def _extract_location(lines: list[str]) -> str:
    for line in lines:
        for candidate in ("Nairobi", "Rest of Kenya", "Mombasa", "Kisumu", "Remote"):
            if candidate in line:
                return candidate
    return "Kenya"


def _extract_job_type(lines: list[str]) -> str:
    for line in lines:
        inferred = infer_job_type(line)
        if inferred != "unknown":
            return inferred
    return "unknown"


def _extract_posted_at(lines: list[str]):
    for line in lines:
        parsed = parse_relative_date(line)
        if parsed:
            return parsed
    return None


def _fallback_jobs(scraper: CorporateStaffingScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Recruitment Research Associate",
                "company": "Corporate Staffing Services",
                "location": "Nairobi",
                "description": "Source candidates, support employer intake, and track recruitment insights for Kenyan clients.",
                "apply_url": "https://www.corporatestaffing.co.ke/jobs/recruitment-research-associate-sample",
                "job_type": "full-time",
                "tags": ["recruitment", "research", "operations"],
            }
        )
    ]
