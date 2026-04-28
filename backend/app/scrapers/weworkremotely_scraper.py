import xml.etree.ElementTree as ET

from .base import BaseScraper
from ..config import settings
from ..models import JobRecord, JobSource


class WeWorkRemotelyScraper(BaseScraper):
    source = JobSource.weworkremotely
    endpoint = "https://weworkremotely.com/remote-jobs.rss"

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        errors: list[str] = []
        jobs: list[JobRecord] = []

        try:
            response = await self.fetch(self.endpoint)
            root = ET.fromstring(response.text)
            for item in root.findall("./channel/item"):
                title = (item.findtext("title") or "").strip()
                company = (item.findtext("{https://weworkremotely.com}company") or "Unknown company").strip()
                location = (item.findtext("{https://weworkremotely.com}region") or "Remote").strip()
                job = self.maybe_build_job(
                    {
                        "title": title or "Unknown role",
                        "company": company,
                        "location": location,
                        "description": item.findtext("description") or "",
                        "description_html": item.findtext("description") or "",
                        "job_url": item.findtext("link") or "https://weworkremotely.com/",
                        "apply_url": item.findtext("link") or "https://weworkremotely.com/",
                        "job_type": item.findtext("category") or "",
                        "skills": _infer_tags(title),
                        "posted_at": item.findtext("pubDate"),
                        "source_website": "weworkremotely.com",
                    }
                )
                if job:
                    jobs.append(job)
        except Exception as exc:
            errors.append(f"WeWorkRemotely fetch failed: {exc}")
            if settings.enable_demo_fallback_jobs:
                jobs.extend(
                    [
                        self.build_job(
                            {
                                "title": "Full-Stack JavaScript Engineer",
                                "company": "Remote Foundry",
                                "location": "Remote",
                                "description": "Ship customer-facing features and maintain API integrations.",
                                "job_url": "https://weworkremotely.com/remote-jobs/sample-fullstack-engineer",
                                "apply_url": "https://weworkremotely.com/remote-jobs/sample-fullstack-engineer",
                                "job_type": "full-time",
                                "skills": ["react", "node.js", "postgresql"],
                                "source_type": "demo",
                                "source_website": "weworkremotely.com",
                            }
                        )
                    ]
                )

        return jobs, errors


def _infer_tags(title: str) -> list[str]:
    title_lower = title.lower()
    tags: list[str] = []
    for keyword in ["python", "react", "javascript", "golang", "devops", "data"]:
        if keyword in title_lower:
            tags.append(keyword)
    return tags
