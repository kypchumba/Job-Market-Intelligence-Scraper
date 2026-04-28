import asyncio
import re

from bs4 import BeautifulSoup

from .african_board_common import (
    absolute_href,
    extract_listing_container,
    extract_text_lines,
    find_links,
    parse_relative_date,
    unique_jobs,
)
from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource
from ..parsers.job_detail_parser import DetailSelectors


MYJOBMAG_SELECTORS = DetailSelectors(
    title=("h1",),
    company=("a[href*='view-jobs-at']",),
    description=("main",),
)


class MyJobMagScraper(BaseScraper):
    source = JobSource.myjobmag

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.myjobmag_pages:
            try:
                async for current_url, soup, _ in self.iterate_result_pages(page_url, page_param="page"):
                    page_jobs, page_errors = await self._extract_jobs(soup, current_url)
                    jobs.extend(page_jobs)
                    errors.extend(page_errors)
            except Exception as exc:
                errors.append(f"MyJobMag page '{page_url}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    async def _extract_jobs(self, soup: BeautifulSoup, page_url: str) -> tuple[list[JobRecord], list[str]]:
        listings: list[dict] = []
        errors: list[str] = []

        for link in find_links(soup, ("/job/",)):
            href = link.get("href", "")
            title_text = " ".join(link.stripped_strings)
            if not title_text or len(title_text) < 6:
                continue

            container = extract_listing_container(link)
            lines = extract_text_lines(container)
            description = " ".join(line for line in lines if line != title_text)
            role, company = _split_title_and_company(title_text)
            posted_at = _extract_posted_at(lines)
            apply_url = absolute_href(page_url, href)
            listings.append(
                {
                    "title": role,
                    "company": company,
                    "location": _extract_location(description, page_url),
                    "description": description,
                    "job_url": apply_url,
                    "apply_url": apply_url,
                    "job_type": "unknown",
                    "skills": self.infer_tags(role, company, description),
                    "posted_at": posted_at or None,
                    "source_website": "myjobmag.co.ke" if ".co.ke" in page_url else "myjobmag.com",
                }
            )

        tasks = [self._build_detail_job(listing, page_url) for listing in listings[: settings.max_detail_jobs_per_source]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        jobs: list[JobRecord] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(f"MyJobMag detail fetch failed: {result}")
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
                selectors=MYJOBMAG_SELECTORS,
                referer=referer,
            )
            page_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
            metadata = _parse_detail_metadata(page_text)
            payload = self.merge_payloads(detail_payload, metadata, listing)
            return self.maybe_build_job(payload), None
        except Exception as exc:
            fallback_job = self.maybe_build_job(listing)
            return fallback_job, f"MyJobMag listing '{listing['job_url']}' detail parsing degraded: {exc}"


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


def _parse_detail_metadata(page_text: str) -> dict:
    metadata: dict = {}
    posted_match = re.search(r"Posted:\s*(.+)", page_text)
    if posted_match:
        metadata["posted_at"] = posted_match.group(1).splitlines()[0].strip()

    job_type_match = re.search(r"Job Type\s+([^\n]+)", page_text)
    if job_type_match:
        metadata["job_type"] = job_type_match.group(1).splitlines()[0].strip()

    experience_match = re.search(r"Experience\s+([^\n]+)", page_text)
    if experience_match:
        metadata["experience_level"] = experience_match.group(1).splitlines()[0].strip()

    location_match = re.search(r"Location\s+([^\n]+)", page_text)
    if location_match:
        metadata["location"] = location_match.group(1).splitlines()[0].strip()

    company_match = re.search(r"View Jobs at\s+([^\n]+)", page_text)
    if company_match:
        metadata["company"] = company_match.group(1).splitlines()[0].strip()

    description = _slice_between(
        page_text,
        start_markers=("Description",),
        end_markers=("Method of Application", "Jobs You Might Be Interested in", "Career Advice"),
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


def _fallback_jobs(scraper: MyJobMagScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Program Data Analyst",
                "company": "African Growth Partners",
                "location": "Nairobi",
                "description": "Support labor-market analytics, reporting, and dashboard automation for regional hiring programs.",
                "job_url": "https://www.myjobmag.co.ke/job/program-data-analyst-sample",
                "apply_url": "https://www.myjobmag.co.ke/job/program-data-analyst-sample",
                "job_type": "full-time",
                "skills": ["data", "python", "analytics"],
                "source_type": "demo",
                "source_website": "myjobmag.co.ke",
            }
        )
    ]
