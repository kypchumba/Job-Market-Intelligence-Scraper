import asyncio
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
from ..parsers.job_detail_parser import DetailSelectors


BRIGHTERMONDAY_SELECTORS = DetailSelectors(
    title=("h1",),
    company=("h2",),
    location=("main",),
    description=("main",),
)


class BrighterMondayScraper(BaseScraper):
    source = JobSource.brightermonday

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.brightermonday_pages:
            try:
                async for current_url, soup, _ in self.iterate_result_pages(page_url, page_param="page"):
                    page_jobs, page_errors = await self._extract_jobs(soup, current_url)
                    jobs.extend(page_jobs)
                    errors.extend(page_errors)
            except Exception as exc:
                errors.append(f"BrighterMonday page '{page_url}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    async def _extract_jobs(self, soup: BeautifulSoup, page_url: str) -> tuple[list[JobRecord], list[str]]:
        listings: list[dict] = []
        errors: list[str] = []

        for link in find_links(soup, ("/listings/", "/job/")):
            title = " ".join(link.stripped_strings)
            if not title or len(title) < 4 or title.lower() in {"homepage", "search results"}:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            company = _extract_company(lines, title)
            location = _extract_location(lines)
            description = _extract_description(lines, title, company)
            posted_at = _extract_posted_at(lines)
            apply_url = absolute_href(page_url, link.get("href"))
            listings.append(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": description,
                    "job_url": apply_url,
                    "apply_url": apply_url,
                    "job_type": _extract_job_type(lines),
                    "salary_text": _extract_salary(lines),
                    "skills": self.infer_tags(title, company, description),
                    "posted_at": posted_at or None,
                    "source_website": "brightermonday.co.ke",
                }
            )

        tasks = [self._build_detail_job(listing, page_url) for listing in listings[: settings.max_detail_jobs_per_source]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        jobs: list[JobRecord] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(f"BrighterMonday detail fetch failed: {result}")
                continue
            job, error = result
            if error:
                errors.append(error)
            if job:
                jobs.append(job)

        return jobs, errors

    async def _build_detail_job(self, listing: dict, referer: str) -> tuple[JobRecord | None, str | None]:
        try:
            detail_payload, html = await self.enrich_detail_payload(
                listing["job_url"],
                defaults=listing,
                selectors=BRIGHTERMONDAY_SELECTORS,
                referer=referer,
            )
            page_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
            metadata = _parse_detail_metadata(page_text)
            payload = self.merge_payloads(detail_payload, metadata, listing)
            return self.maybe_build_job(payload), None
        except Exception as exc:
            fallback_job = self.maybe_build_job(listing)
            return fallback_job, f"BrighterMonday listing '{listing['job_url']}' detail parsing degraded: {exc}"


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


def _extract_salary(lines: list[str]) -> str | None:
    joined = " ".join(lines)
    match = re.search(r"(KSh\s+[^A-Z\n]+|Confidential)", joined)
    if match:
        return match.group(1).strip()
    return None


def _extract_description(lines: list[str], title: str, company: str) -> str:
    ignored = {title, company, "FEATURED", "New", "Popular", "Easy apply"}
    body = [line for line in lines if line not in ignored and infer_job_type(line) == "unknown"]
    return " ".join(body[:8])


def _extract_posted_at(lines: list[str]):
    for line in lines:
        parsed = parse_relative_date(line)
        if parsed:
            return parsed
    return None


def _parse_detail_metadata(page_text: str) -> dict:
    metadata: dict = {}

    location_match = re.search(r"Applicant Location:\s*([^\n]+)", page_text)
    if location_match:
        metadata["location"] = location_match.group(1).strip()

    experience_match = re.search(r"Experience Level:\s*([^\n]+?)(?:Experience Length:|Applicant Location:)", page_text)
    if experience_match:
        metadata["experience_level"] = experience_match.group(1).strip()

    job_type_match = re.search(r"\b(Full Time|Contract|Part Time|Internship & Graduate)\b", page_text)
    if job_type_match:
        metadata["job_type"] = job_type_match.group(1)

    salary_match = re.search(r"(KSh\s+[^\n]+|Confidential)", page_text)
    if salary_match:
        metadata["salary_text"] = salary_match.group(1).strip()

    description = _slice_between(
        page_text,
        start_markers=("Job descriptions & requirements",),
        end_markers=("Important safety tips", "Log in to apply now", "Similar jobs"),
    )
    if description:
        metadata["description"] = description
        metadata["description_html"] = description
    return metadata


def _slice_between(text: str, *, start_markers: tuple[str, ...], end_markers: tuple[str, ...]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    started = False
    collected: list[str] = []

    for line in lines:
        if not started and any(line == marker for marker in start_markers):
            started = True
            continue
        if started and any(line.startswith(marker) for marker in end_markers):
            break
        if started:
            collected.append(line)

    return " ".join(collected)


def _fallback_jobs(scraper: BrighterMondayScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Regional Sales Operations Analyst",
                "company": "East Africa Talent Hub",
                "location": "Nairobi",
                "description": "Analyze hiring funnel performance and support employer partnerships across East African markets.",
                "job_url": "https://www.brightermonday.co.ke/listings/regional-sales-operations-analyst-sample",
                "apply_url": "https://www.brightermonday.co.ke/listings/regional-sales-operations-analyst-sample",
                "job_type": "full-time",
                "skills": ["data", "sales", "operations"],
                "source_type": "demo",
                "source_website": "brightermonday.co.ke",
            }
        )
    ]
