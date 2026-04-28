import re

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
                async for current_url, soup, _ in self.iterate_result_pages(page_url):
                    jobs.extend(self._extract_jobs(soup, current_url))
            except Exception as exc:
                errors.append(f"Corporate Staffing page '{page_url}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    def _extract_jobs(self, soup: BeautifulSoup, page_url: str) -> list[JobRecord]:
        jobs: list[JobRecord] = []

        for link in find_links(soup, ("/job/", "/jobs/")):
            title = " ".join(link.stripped_strings)
            if not title or len(title) < 6:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            description = _extract_description(lines, title)
            company = _extract_company(title, description)
            payload = {
                "title": title,
                "company": company,
                "location": _extract_location(title, description),
                "description": description,
                "job_url": absolute_href(page_url, link.get("href")),
                "apply_url": absolute_href(page_url, link.get("href")),
                "job_type": _extract_job_type(lines, description),
                "salary_text": _extract_salary(title, description),
                "skills": self.infer_tags(title, description, company),
                "posted_at": _extract_posted_at(lines) or None,
                "source_website": "corporatestaffing.co.ke",
            }
            job = self.maybe_build_job(payload)
            if job:
                jobs.append(job)

        return jobs


def _extract_company(title: str, description: str) -> str:
    for text in (title, description):
        match = re.search(r"([A-Z][A-Za-z0-9&.\-\s]{2,60})\s+Jobs", text)
        if match:
            return match.group(1).strip(" .")
    return "Corporate Staffing Services"


def _extract_location(title: str, description: str) -> str:
    combined = f"{title} {description}"
    for candidate in ("Nairobi", "Mombasa", "Kisumu", "Nakuru", "Kakamega", "Rest of Kenya", "Remote"):
        if candidate.lower() in combined.lower():
            return candidate
    return "Kenya"


def _extract_job_type(lines: list[str], description: str) -> str:
    for line in lines:
        inferred = infer_job_type(line)
        if inferred != "unknown":
            return inferred
    return infer_job_type(description)


def _extract_salary(title: str, description: str) -> str | None:
    for text in (title, description):
        match = re.search(r"(\d[\d,]*(?:\.\d+)?\s*[Kk]\s*(?:-|to|–)\s*\d[\d,]*(?:\.\d+)?\s*[Kk]|\d[\d,]*(?:\.\d+)?\s*[Kk])", text)
        if match:
            return match.group(1).strip()
    return None


def _extract_description(lines: list[str], title: str) -> str:
    ignored = {title, "Page navigation"}
    body = [line for line in lines if line not in ignored]
    return " ".join(body[:8])[:1600]


def _extract_posted_at(lines: list[str]):
    for line in lines:
        parsed = parse_relative_date(line)
        if parsed:
            return parsed
        if re.search(r"\b\d{4}\b", line):
            return line
    return None


def _fallback_jobs(scraper: CorporateStaffingScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Recruitment Research Associate",
                "company": "Corporate Staffing Services",
                "location": "Nairobi",
                "description": "Source candidates, support employer intake, and track recruitment insights for Kenyan clients.",
                "job_url": "https://www.corporatestaffing.co.ke/jobs/recruitment-research-associate-sample",
                "apply_url": "https://www.corporatestaffing.co.ke/jobs/recruitment-research-associate-sample",
                "job_type": "full-time",
                "skills": ["recruitment", "research", "operations"],
                "source_type": "demo",
                "source_website": "corporatestaffing.co.ke",
            }
        )
    ]
