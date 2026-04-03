import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def extract_listing_container(link):
    for tag in ("article", "li", "section", "div"):
        container = link.find_parent(tag)
        if container:
            return container
    return link


def extract_text_lines(node) -> list[str]:
    return [line.strip() for line in node.get_text("\n", strip=True).splitlines() if line.strip()]


def infer_job_type(*values: str) -> str:
    text = " ".join(value for value in values if value).lower()
    for label in ("full time", "full-time", "contract", "part time", "part-time", "internship", "remote"):
        if label in text:
            return label.replace(" ", "-")
    return "unknown"


def parse_relative_date(value: str) -> datetime | None:
    text = (value or "").strip().lower()
    now = datetime.now(timezone.utc)
    if text == "today":
        return now
    if text == "yesterday":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    match = re.search(r"(\d+)\s+(day|days|week|weeks)\s+ago", text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        delta_days = amount * 7 if "week" in unit else amount
        return now.fromtimestamp(now.timestamp() - (delta_days * 86400), tz=timezone.utc)

    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)", value or "")
    if match:
        candidate = f"{match.group(1)} {match.group(2)} {now.year}"
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(candidate, fmt).replace(tzinfo=timezone.utc)
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
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if any(pattern in href for pattern in href_patterns):
            yield link
