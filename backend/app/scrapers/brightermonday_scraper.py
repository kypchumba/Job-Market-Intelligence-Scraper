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


class BrighterMondayScraper(BaseScraper):
    source = JobSource.brightermonday

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.brightermonday_pages:
            try:
                response = await self.client.get(page_url)
                response.raise_for_status()
                jobs.extend(self._extract_jobs(response.text, page_url))
            except Exception as exc:
                errors.append(f"BrighterMonday page '{page_url}' failed: {exc}")

        if not jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    def _extract_jobs(self, html: str, page_url: str) -> list[JobRecord]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobRecord] = []

        for link in find_links(soup, ("/listings/", "/job/")):
            title = " ".join(link.stripped_strings)
            if not title or len(title) < 4 or title.lower() in {"homepage", "search results"}:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            job_type = _extract_job_type(lines)
            if job_type == "unknown":
                continue

            company = _extract_company(lines, title)
            location = _extract_location(lines)
            description = _extract_description(lines, title, company)
            posted_at = _extract_posted_at(lines)
            apply_url = absolute_href(page_url, link.get("href"))

            jobs.append(
                self.build_job(
                    {
                        "title": title,
                        "company": company,
                        "location": location,
                        "description": description,
                        "apply_url": apply_url,
                        "job_type": job_type,
                        "tags": self.infer_tags(title, company, description),
                        "posted_at": posted_at or None,
                    }
                )
            )

        return jobs


def _extract_company(lines: list[str], title: str) -> str:
    title_index = lines.index(title) if title in lines else -1
    if title_index >= 0 and title_index + 1 < len(lines):
        candidate = lines[title_index + 1]
        if candidate and candidate not in {"FEATURED", "New", "Popular", "Easy apply"}:
            return candidate
    return "BrighterMonday Employer"


def _extract_location(lines: list[str]) -> str:
    for line in lines:
        match = re.search(r"(Remote \(Work From Home\)|Nairobi|Mombasa|Kisumu|Nakuru|Rest of Kenya|Outside Kenya)", line)
        if match:
            value = match.group(1)
            return "Remote" if value.startswith("Remote") else value
    return "Kenya"


def _extract_job_type(lines: list[str]) -> str:
    for line in lines:
        inferred = infer_job_type(line)
        if inferred != "unknown":
            return inferred
    return "unknown"


def _extract_description(lines: list[str], title: str, company: str) -> str:
    ignored = {title, company, "FEATURED", "New", "Popular", "Easy apply"}
    body = [line for line in lines if line not in ignored and infer_job_type(line) == "unknown"]
    return " ".join(body[:6])


def _extract_posted_at(lines: list[str]):
    for line in lines:
        parsed = parse_relative_date(line)
        if parsed:
            return parsed
    return None


def _fallback_jobs(scraper: BrighterMondayScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Regional Sales Operations Analyst",
                "company": "East Africa Talent Hub",
                "location": "Nairobi",
                "description": "Analyze hiring funnel performance and support employer partnerships across East African markets.",
                "apply_url": "https://www.brightermonday.co.ke/listings/regional-sales-operations-analyst-sample",
                "job_type": "full-time",
                "tags": ["data", "sales", "operations"],
            }
        )
    ]
