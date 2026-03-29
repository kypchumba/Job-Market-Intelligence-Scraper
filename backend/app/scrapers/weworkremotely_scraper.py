import xml.etree.ElementTree as ET

from .base import BaseScraper
from ..models import JobRecord, JobSource


class WeWorkRemotelyScraper(BaseScraper):
    source = JobSource.weworkremotely
    endpoint = "https://weworkremotely.com/remote-jobs.rss"

    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        errors: list[str] = []
        jobs: list[JobRecord] = []

        try:
            response = await self.client.get(self.endpoint)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            for item in root.findall("./channel/item"):
                title = (item.findtext("title") or "").strip()
                company = (item.findtext("{https://weworkremotely.com}company") or "Unknown company").strip()
                location = (item.findtext("{https://weworkremotely.com}region") or "Remote").strip()
                jobs.append(
                    self.build_job(
                        {
                            "title": title or "Unknown role",
                            "company": company,
                            "location": location,
                            "description": item.findtext("description") or "",
                            "apply_url": item.findtext("link") or "https://weworkremotely.com/",
                            "job_type": "remote",
                            "tags": _infer_tags(title),
                        }
                    )
                )
        except Exception as exc:
            errors.append(f"WeWorkRemotely fetch failed: {exc}")
            jobs.extend(
                [
                    self.build_job(
                        {
                            "title": "Full-Stack JavaScript Engineer",
                            "company": "Remote Foundry",
                            "location": "Remote",
                            "description": "Ship customer-facing features and maintain API integrations.",
                            "apply_url": "https://weworkremotely.com/remote-jobs/sample-fullstack-engineer",
                            "job_type": "full-time",
                            "tags": ["react", "node.js", "postgresql"],
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
