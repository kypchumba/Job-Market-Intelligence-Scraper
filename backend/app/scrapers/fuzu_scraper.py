import asyncio
import re

from bs4 import BeautifulSoup

from .african_board_common import absolute_href, find_links, unique_jobs
from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource
from ..parsers.job_detail_parser import DetailSelectors


FUZU_SELECTORS = DetailSelectors(
    title=("h1",),
    company=("main",),
    location=("main",),
    description=("main",),
)


class FuzuScraper(BaseScraper):
    source = JobSource.fuzu

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        for page_url in settings.fuzu_pages:
            try:
                async for current_url, soup, _ in self.iterate_result_pages(page_url, page_param="page"):
                    page_jobs, page_errors = await self._extract_jobs(soup, current_url)
                    jobs.extend(page_jobs)
                    errors.extend(page_errors)
            except Exception as exc:
                errors.append(f"Fuzu page '{page_url}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return unique_jobs(jobs), errors

    async def _extract_jobs(self, soup: BeautifulSoup, page_url: str) -> tuple[list[JobRecord], list[str]]:
        listings: list[dict] = []
        errors: list[str] = []

        for link in find_links(soup, ("/job/",)):
            href = link.get("href", "")
            if href.rstrip("/") in {"", "/job"}:
                continue
            text = " ".join(link.stripped_strings)
            if "get personalised job alerts" in text.lower():
                continue

            job_url = absolute_href(page_url, href)
            listings.append(
                {
                    "title": text or "Unknown role",
                    "company": "Fuzu Employer",
                    "location": "Africa",
                    "description": text,
                    "job_url": job_url,
                    "apply_url": job_url,
                    "job_type": "unknown",
                    "source_website": "fuzu.com",
                }
            )

        tasks = [self._build_detail_job(listing, page_url) for listing in listings[: settings.max_detail_jobs_per_source]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        jobs: list[JobRecord] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(f"Fuzu detail fetch failed: {result}")
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
                selectors=FUZU_SELECTORS,
                referer=referer,
            )
            page_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
            metadata = _parse_detail_metadata(page_text)
            payload = self.merge_payloads(detail_payload, metadata, listing)
            return self.maybe_build_job(payload), None
        except Exception as exc:
            fallback_job = self.maybe_build_job(listing)
            return fallback_job, f"Fuzu listing '{listing['job_url']}' detail parsing degraded: {exc}"


def _parse_detail_metadata(page_text: str) -> dict:
    metadata: dict = {}
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]

    title_index = next((index for index, line in enumerate(lines) if line and not line.startswith("[")), -1)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title_index = index
            metadata["title"] = line.removeprefix("# ").strip()
            break

    if title_index > 0:
        metadata["company"] = lines[title_index - 2] if title_index >= 2 else lines[title_index - 1]

    location_match = re.search(r"\b(Nairobi|Mombasa|Kisumu|Nakuru|Kampala|Lagos|Abuja|Ibadan|Jinja|Mukono)\b.*?\b(Kenya|Uganda|Nigeria)\b", page_text, re.IGNORECASE)
    if location_match:
        metadata["location"] = f"{location_match.group(1).title()}, {location_match.group(2).title()}"

    tags_match = re.findall(r"\b(Entry-level|Entry and Basic-level|Mid-level|Senior-level)\b", page_text, re.IGNORECASE)
    if tags_match:
        metadata["experience_level"] = tags_match[0]

    description = _slice_between(
        lines,
        start_markers=("Description", "Responsibilities"),
        end_markers=("Tags", "Start hiring with Fuzu", "Job search tips from Fuzu"),
    )
    if description:
        metadata["description"] = description
        metadata["description_html"] = description

    skills = re.findall(r"\b([A-Z][A-Za-z]+(?:,\s*[A-Za-z]+)?)\b", description or "")
    if skills:
        metadata["skills"] = skills[:8]
    return metadata


def _slice_between(lines: list[str], *, start_markers: tuple[str, ...], end_markers: tuple[str, ...]) -> str:
    started = False
    collected: list[str] = []
    for line in lines:
        if not started and line in start_markers:
            started = True
            continue
        if started and any(line.startswith(marker) for marker in end_markers):
            break
        if started:
            collected.append(line)
    return " ".join(collected)


def _fallback_jobs(scraper: FuzuScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Talent Intelligence Coordinator",
                "company": "Fuzu Partner Employer",
                "location": "Nairobi, Kenya",
                "description": "Coordinate candidate pipelines, reporting, and employer communications across the Fuzu marketplace.",
                "job_url": "https://www.fuzu.com/job/talent-intelligence-coordinator-sample",
                "apply_url": "https://www.fuzu.com/job/talent-intelligence-coordinator-sample",
                "job_type": "full-time",
                "skills": ["operations", "data", "recruitment"],
                "source_type": "demo",
                "source_website": "fuzu.com",
            }
        )
    ]
