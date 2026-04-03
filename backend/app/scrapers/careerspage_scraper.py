import json

from bs4 import BeautifulSoup

from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class CareersPageScraper(BaseScraper):
    source = JobSource.careerspage

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        jobs: list[JobRecord] = []
        errors: list[str] = []

        page_urls = [*settings.careers_pages, *settings.ngo_pages]

        for page_url in page_urls:
            try:
                response = await self.client.get(page_url)
                response.raise_for_status()
                jobs.extend(self._extract_jobs(response.text, page_url))
            except Exception as exc:
                errors.append(f"Careers page '{page_url}' failed: {exc}")

        if not jobs:
            jobs.extend(_fallback_jobs(self))

        return jobs, errors

    def _extract_jobs(self, html: str, page_url: str) -> list[JobRecord]:
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        jobs: list[JobRecord] = []

        for script in scripts:
            if not script.string:
                continue
            try:
                payload = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            for item in _flatten_ld_json(payload):
                if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                    continue
                company = (
                    ((item.get("hiringOrganization") or {}).get("name"))
                    or self.domain_company_name(page_url)
                )
                location = _job_location(item.get("jobLocation")) or "Remote"
                description = self.html_to_text(item.get("description", ""))
                jobs.append(
                    self.build_job(
                        {
                            "title": item.get("title", "Unknown role"),
                            "company": company,
                            "location": location,
                            "description": description,
                            "apply_url": item.get("url") or page_url,
                            "job_type": _employment_type(item.get("employmentType")),
                            "tags": self.infer_tags(item.get("title", ""), description, company),
                            "posted_at": item.get("datePosted"),
                        }
                    )
                )

        return jobs


def _flatten_ld_json(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from _flatten_ld_json(item)
    elif isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _flatten_ld_json(item)
        else:
            yield payload


def _job_location(value) -> str:
    if isinstance(value, list) and value:
        return _job_location(value[0])
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            return ", ".join(part for part in parts if part)
    return ""


def _employment_type(value) -> str:
    if isinstance(value, list) and value:
        return str(value[0]).lower()
    if isinstance(value, str):
        return value.lower()
    return "unknown"


def _fallback_jobs(scraper: CareersPageScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Developer Experience Engineer",
                "company": "Example Careers Page",
                "location": "Remote",
                "description": "Own developer tooling, docs, and internal platform workflows.",
                "apply_url": "https://careers.example.com/jobs/developer-experience-engineer",
                "job_type": "full-time",
                "tags": ["python", "devops", "developer-experience"],
            }
        )
    ]
