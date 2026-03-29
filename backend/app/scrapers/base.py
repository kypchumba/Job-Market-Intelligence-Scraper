from abc import ABC, abstractmethod
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from ..models import JobRecord, JobSource
from ..services.normalizer import normalize_job


class BaseScraper(ABC):
    source: JobSource

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            headers={
                "User-Agent": "JobIntelBot/0.1 (+https://localhost)",
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
        )

    @abstractmethod
    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        raise NotImplementedError

    async def close(self) -> None:
        await self.client.aclose()

    def build_job(self, payload: dict) -> JobRecord:
        return normalize_job(payload, self.source)

    @staticmethod
    def parse_datetime(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    @staticmethod
    def infer_tags(*values: str) -> list[str]:
        text = " ".join(value for value in values if value).lower()
        keywords = [
            "python",
            "react",
            "javascript",
            "typescript",
            "java",
            "golang",
            "devops",
            "data",
            "backend",
            "frontend",
            "full stack",
            "product",
        ]
        tags: list[str] = []
        for keyword in keywords:
            if keyword in text:
                tags.append(keyword.replace(" ", "-"))
        return tags

    @staticmethod
    def html_to_text(value: str) -> str:
        if not value:
            return ""
        return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)

    @staticmethod
    def domain_company_name(url: str) -> str:
        hostname = urlparse(url).hostname or "Unknown company"
        root = hostname.replace("www.", "").split(".")[0]
        return root.replace("-", " ").replace("_", " ").title()
