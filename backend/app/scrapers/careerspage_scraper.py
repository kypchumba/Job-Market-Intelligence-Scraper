import json

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
                response = await self.fetch(page_url)
                jobs.extend(self._extract_jobs(response.text, page_url))
            except Exception as exc:
                errors.append(f"Careers page '{page_url}' failed: {exc}")

        if not jobs and settings.enable_demo_fallback_jobs:
            jobs.extend(_fallback_jobs(self))

        return jobs, errors

    def _extract_jobs(self, html: str, page_url: str) -> list[JobRecord]:
        payloads = []
        scripts = _extract_ld_json_payloads(html)

        for item in scripts:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            company = ((item.get("hiringOrganization") or {}).get("name")) or self.domain_company_name(page_url)
            location = _job_location(item.get("jobLocation")) or item.get("jobLocationType") or "Remote"
            description_html = item.get("description", "")
            description = self.html_to_text(description_html)
            payloads.append(
                {
                    "title": item.get("title", "Unknown role"),
                    "company": company,
                    "location": location,
                    "description": description,
                    "description_html": description_html,
                    "job_url": item.get("url") or page_url,
                    "apply_url": item.get("url") or page_url,
                    "job_type": _employment_type(item.get("employmentType")),
                    "skills": self.infer_tags(item.get("title", ""), description, company),
                    "posted_at": item.get("datePosted"),
                    "salary_text": _salary_text(item.get("baseSalary")),
                    "source_job_id": _identifier(item.get("identifier")),
                    "source_website": self.domain_company_name(page_url).replace(" ", "").lower(),
                }
            )

        jobs: list[JobRecord] = []
        for payload in payloads:
            job = self.maybe_build_job(payload)
            if job:
                jobs.append(job)
        return jobs


def _extract_ld_json_payloads(html: str):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        yield from _flatten_ld_json(payload)


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


def _salary_text(value) -> str | None:
    if not isinstance(value, dict):
        return None
    currency = value.get("currency") or value.get("currencyCode") or ""
    inner = value.get("value")
    if isinstance(inner, dict):
        minimum = inner.get("minValue")
        maximum = inner.get("maxValue")
        if minimum and maximum:
            return f"{currency} {minimum} - {maximum}"
        if minimum:
            return f"{currency} {minimum}"
    return None


def _identifier(value) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("value") or value.get("name")
        return str(candidate).strip() if candidate else None
    if value:
        return str(value).strip()
    return None


def _fallback_jobs(scraper: CareersPageScraper) -> list[JobRecord]:
    return [
        scraper.build_job(
            {
                "title": "Developer Experience Engineer",
                "company": "Example Careers Page",
                "location": "Remote",
                "description": "Own developer tooling, docs, and internal platform workflows.",
                "job_url": "https://careers.example.com/jobs/developer-experience-engineer",
                "apply_url": "https://careers.example.com/jobs/developer-experience-engineer",
                "job_type": "full-time",
                "skills": ["python", "devops", "developer-experience"],
                "source_type": "demo",
                "source_website": "careers.example.com",
            }
        )
    ]
