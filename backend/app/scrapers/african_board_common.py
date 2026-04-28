from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..services.normalizer import normalize_job_type, normalize_whitespace


BLOCKED_LINK_TEXT = {
    "homepage",
    "search results",
    "view all latest jobs today",
    "back to home",
    "login",
    "sign up",
}


def extract_listing_container(link):
    for tag in ("article", "li", "section", "div"):
        container = link.find_parent(tag)
        if container:
            return container
    return link


def extract_text_lines(node) -> list[str]:
    return [line.strip() for line in node.get_text("\n", strip=True).splitlines() if line.strip()]


def infer_job_type(*values: str) -> str:
    return normalize_job_type(" ".join(value for value in values if value))


def parse_relative_date(value: str) -> datetime | None:
    text = normalize_whitespace(value or "")
    lowered = text.lower()
    now = datetime.now(timezone.utc)
    if not text:
        return None
    if lowered == "today":
        return now
    if lowered == "yesterday":
        return now - timedelta(days=1)

    relative = re.search(r"(\d+)\s+(day|days|week|weeks|month|months)\s+ago", lowered)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        multiplier = 30 if "month" in unit else 7 if "week" in unit else 1
        return now - timedelta(days=amount * multiplier)

    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def absolute_href(base_url: str, href: str | None) -> str:
    if not href:
        return base_url
    return urljoin(base_url, href)


def unique_jobs(jobs):
    seen: set[str] = set()
    unique = []
    for job in jobs:
        if job.id in seen:
            continue
        seen.add(job.id)
        unique.append(job)
    return unique


def find_links(soup: BeautifulSoup, href_patterns: tuple[str, ...]):
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = normalize_whitespace(" ".join(link.stripped_strings)).lower()
        if href in seen or text in BLOCKED_LINK_TEXT:
            continue
        if any(pattern in href for pattern in href_patterns):
            seen.add(href)
            yield link


def find_next_page_url(soup: BeautifulSoup, base_url: str) -> str | None:
    selectors = (
        "a[rel='next']",
        "a[aria-label*='Next']",
        "a[title*='Next']",
        ".pagination a",
        "nav[aria-label*='Pagination'] a",
    )
    for selector in selectors:
        for node in soup.select(selector):
            text = normalize_whitespace(node.get_text(" ", strip=True)).lower()
            href = node.get("href")
            if href and any(marker in text for marker in ("next", "older", "go to next page")):
                return absolute_href(base_url, href)
    return None


def build_paged_url(base_url: str, page_number: int, page_param: str = "page") -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query, keep_blank_values=False)
    query[page_param] = [str(page_number)]
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query, doseq=True),
            parsed.fragment,
        )
    )
