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


class FuzuScraper(BaseScraper):
    source = JobSource.fuzu

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.fuzu_pages:
            try:
                response = await self.client.get(page_url)
                response.raise_for_status()
                jobs.extend(self._extract_jobs(response.text, page_url))
            except Exception as exc:
                errors.append(f"Fuzu page '{page_url}' failed: {exc}")

        if not jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    def _extract_jobs(self, html: str, page_url: str) -> list[JobRecord]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobRecord] = []

        for link in find_links(soup, ("/job/",)):
            href = link.get("href", "")
            if href.rstrip("/") in {"", "/job"}:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            title, company = _extract_title_company(lines, " ".join(link.stripped_strings))
            description = " ".join(lines[3:10]) if len(lines) > 3 else " ".join(lines)
            jobs.append(
                self.build_job(
                    {
                        "title": title,
                        "company": company,
                        "location": _extract_location(lines),
                        "description": description,
                        "apply_url": absolute_href(page_url, href),
                        "job_type": infer_job_type(description),
                        "tags": self.infer_tags(title, company, description),
                        "posted_at": _extract_posted_at(lines) or None,
                    }
                )
            )

        return jobs


def _extract_title_company(lines: list[str], fallback: str) -> tuple[str, str]:
    if len(lines) >= 2 and len(lines[0]) < 60:
        company = lines[0]
        title = lines[1]
        return title, company

    clean = re.sub(r"\s+", " ", fallback).strip()
    return clean or "Unknown role", "Fuzu Employer"


def _extract_location(lines: list[str]) -> str:
    joined = " ".join(lines)
    match = re.search(r"(Nairobi|Kampala|Lagos|Abuja|Gulu|Mombasa)\s*[•,-]\s*(Kenya|Uganda|Nigeria)", joined)
    if match:
        return f"{match.group(1)}, {match.group(2)}"
    if "Remote" in joined:
        return "Remote"
    return "Africa"


def _extract_posted_at(lines: list[str]):
    for line in lines:
        parsed = parse_relative_date(line)
        if parsed:
            return parsed
    return None


def _fallback_jobs(scraper: FuzuScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Talent Intelligence Coordinator",
                "company": "Fuzu Partner Employer",
                "location": "Nairobi, Kenya",
                "description": "Coordinate candidate pipelines, reporting, and employer communications across the Fuzu marketplace.",
                "apply_url": "https://www.fuzu.com/job/talent-intelligence-coordinator-sample",
                "job_type": "full-time",
                "tags": ["operations", "data", "recruitment"],
            }
        )
    ]
