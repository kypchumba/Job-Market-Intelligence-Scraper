from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from ..models import JobRecord, JobSource
from ..parsers.job_detail_parser import DetailSelectors, extract_job_detail
from ..services.normalizer import (
    clean_html_text,
    extract_skills,
    looks_like_job,
    normalize_job,
    normalize_whitespace,
    parse_datetime,
)
from .african_board_common import build_paged_url, find_next_page_url


class BaseScraper(ABC):
    source: JobSource

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )
        self._rng = random.Random()
        self._last_request_started: dict[str, float] = {}
        self._detail_semaphore = asyncio.Semaphore(settings.detail_request_concurrency)

    @abstractmethod
    async def scrape(self) -> tuple[list[JobRecord], list[str]]:
        raise NotImplementedError

    async def close(self) -> None:
        await self.client.aclose()

    async def fetch(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response:
        last_error = None
        for attempt in range(settings.request_max_retries + 1):
            await self._throttle(url)
            try:
                response = await self.client.get(url, headers=self._build_headers(url, headers))
                if response.status_code in settings.request_retry_statuses:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt >= settings.request_max_retries:
                    raise
                await asyncio.sleep(
                    settings.request_backoff_seconds * (attempt + 1)
                    + self._rng.uniform(0, settings.request_jitter_seconds)
                )
        raise last_error  # pragma: no cover - defensive

    async def iterate_result_pages(
        self,
        start_url: str,
        *,
        page_param: str | None = None,
    ):
        current_url = start_url
        seen_urls: set[str] = set()
        page_number = 1

        while current_url and page_number <= settings.max_pages_per_source and current_url not in seen_urls:
            seen_urls.add(current_url)
            response = await self.fetch(current_url, headers={"Referer": start_url})
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            yield current_url, soup, html

            next_url = find_next_page_url(soup, current_url)
            if not next_url and page_param:
                candidate = build_paged_url(start_url, page_number + 1, page_param=page_param)
                if candidate not in seen_urls:
                    next_url = candidate
            if not next_url:
                break
            current_url = next_url
            page_number += 1

    async def enrich_detail_payload(
        self,
        detail_url: str,
        *,
        defaults: dict | None = None,
        selectors: DetailSelectors | None = None,
        referer: str | None = None,
    ) -> tuple[dict, str]:
        async with self._detail_semaphore:
            response = await self.fetch(detail_url, headers={"Referer": referer or detail_url})
            detail_payload = extract_job_detail(
                response.text,
                detail_url,
                selectors=selectors,
                defaults=defaults,
            )
            return detail_payload, response.text

    def maybe_build_job(self, payload: dict) -> JobRecord | None:
        if not looks_like_job(payload):
            return None
        return normalize_job(payload, self.source)

    def build_job(self, payload: dict) -> JobRecord:
        job = self.maybe_build_job(payload)
        if job is None:
            raise ValueError(f"Rejected non-job payload for {self.source.value}: {payload.get('title', '')}")
        return job

    @staticmethod
    def parse_datetime(value) -> datetime:
        return parse_datetime(value)

    @staticmethod
    def infer_tags(*values: str) -> list[str]:
        joined = " ".join(value for value in values if value)
        return extract_skills(joined, "", "", [])

    @staticmethod
    def html_to_text(value: str) -> str:
        return clean_html_text(value)

    @staticmethod
    def domain_company_name(url: str) -> str:
        hostname = urlparse(url).hostname or "Unknown company"
        root = hostname.replace("www.", "").split(".")[0]
        return root.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def merge_payloads(*payloads: dict) -> dict:
        merged: dict = {}
        for payload in payloads:
            for key, value in payload.items():
                if value in (None, "", [], {}):
                    continue
                if key not in merged or merged[key] in (None, "", [], {}, "unknown", "Unknown company"):
                    merged[key] = value
                    continue
                if key in {"skills", "tags", "aggregated_sources"}:
                    existing = merged.get(key) or []
                    merged[key] = _unique_text_values([*existing, *value]) if isinstance(value, list) else existing
        return merged

    def noise_safe_text(self, value: str) -> str:
        return normalize_whitespace(clean_html_text(value))

    def _build_headers(self, url: str, extra_headers: dict[str, str] | None) -> dict[str, str]:
        user_agent = self._rng.choice(settings.scrape_user_agents)
        hostname = urlparse(url).hostname or "localhost"
        headers = {
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"https://{hostname}/",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def _throttle(self, url: str) -> None:
        hostname = urlparse(url).netloc or "default"
        last_started = self._last_request_started.get(hostname)
        now = time.monotonic()
        if last_started is not None:
            elapsed = now - last_started
            required_delay = settings.request_min_delay_seconds + self._rng.uniform(0, settings.request_jitter_seconds)
            if elapsed < required_delay:
                await asyncio.sleep(required_delay - elapsed)
        self._last_request_started[hostname] = time.monotonic()


def _unique_text_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = normalize_whitespace(str(value)).lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result
