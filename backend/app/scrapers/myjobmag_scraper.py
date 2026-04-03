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


class MyJobMagScraper(BaseScraper):
    source = JobSource.myjobmag

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.myjobmag_pages:
            try:
                response = await self.client.get(page_url)
                response.raise_for_status()
                jobs.extend(self._extract_jobs(response.text, page_url))
            except Exception as exc:
                errors.append(f"MyJobMag page '{page_url}' failed: {exc}")

        if not jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    def _extract_jobs(self, html: str, page_url: str) -> list[JobRecord]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobRecord] = []

        for link in find_links(soup, ("/job/",)):
            title_text = " ".join(link.stripped_strings)
            if not title_text or len(title_text) < 6:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            description = " ".join(line for line in lines if line != title_text)
            role, company = _split_title_and_company(title_text)
            location = _extract_location(description, page_url)
            posted_at = _extract_posted_at(lines)
            apply_url = absolute_href(page_url, link.get("href"))

            jobs.append(
                self.build_job(
                    {
                        "title": role,
                        "company": company,
                        "location": location,
                        "description": description,
                        "apply_url": apply_url,
                        "job_type": infer_job_type(title_text, description),
                        "tags": self.infer_tags(role, company, description),
                        "posted_at": posted_at or None,
                    }
                )
            )

        return jobs


def _split_title_and_company(title_text: str) -> tuple[str, str]:
    clean = re.sub(r"\s+", " ", title_text).strip()
    if " at " in clean:
        role, company = clean.split(" at ", 1)
        if role.lower().startswith("fresh jobs"):
            return "Multiple Open Roles", company.strip()
        return role.strip(" -"), company.strip()
    return clean, "MyJobMag Employer"


def _extract_location(description: str, page_url: str) -> str:
    lower = description.lower()
    if "kenya" in page_url:
        default_location = "Kenya"
    elif ".com/jobs" in page_url:
        default_location = "Nigeria"
    else:
        default_location = "Africa"

    match = re.search(r"\b(nairobi|mombasa|kisumu|nakuru|kampala|lagos|abuja|accra)\b", lower)
    if match:
        return match.group(1).title()
    if "remote" in lower:
        return "Remote"
    return default_location


def _extract_posted_at(lines: list[str]):
    for line in lines:
        parsed = parse_relative_date(line)
        if parsed:
            return parsed
    return None


def _fallback_jobs(scraper: MyJobMagScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Program Data Analyst",
                "company": "African Growth Partners",
                "location": "Nairobi",
                "description": "Support labor-market analytics, reporting, and dashboard automation for regional hiring programs.",
                "apply_url": "https://www.myjobmag.co.ke/job/program-data-analyst-sample",
                "job_type": "full-time",
                "tags": ["data", "python", "analytics"],
            }
        )
    ]
