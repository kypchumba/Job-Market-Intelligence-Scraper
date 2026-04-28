from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


DEFAULT_TEXT_SELECTORS = {
    "title": (
        "h1",
        "[data-testid*='title']",
        "[class*='job-title']",
        "[class*='posting-title']",
        "[class*='listing-title']",
    ),
    "company": (
        "[data-testid*='company']",
        "[class*='company']",
        ".employer-name",
        "h2",
    ),
    "location": (
        "[data-testid*='location']",
        "[class*='location']",
        "[class*='applicant-location']",
    ),
    "job_type": (
        "[data-testid*='job-type']",
        "[class*='employment-type']",
        "[class*='job-type']",
        "[class*='contract-type']",
    ),
    "salary": (
        "[data-testid*='salary']",
        "[class*='salary']",
        "[class*='compensation']",
    ),
    "posted_at": (
        "time",
        "[data-testid*='posted']",
        "[class*='posted']",
        "[class*='date']",
    ),
    "experience": (
        "[data-testid*='experience']",
        "[class*='experience']",
        "[class*='seniority']",
    ),
    "skills": (
        "[data-testid*='tag']",
        "[class*='tag']",
        "[class*='skill']",
    ),
    "description": (
        "[data-testid*='description']",
        "[class*='job-description']",
        "[class*='description']",
        "[class*='job-details']",
        "article",
        "main",
    ),
}


@dataclass(frozen=True)
class DetailSelectors:
    title: tuple[str, ...] = ()
    company: tuple[str, ...] = ()
    location: tuple[str, ...] = ()
    job_type: tuple[str, ...] = ()
    salary: tuple[str, ...] = ()
    posted_at: tuple[str, ...] = ()
    description: tuple[str, ...] = ()
    apply_url: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    experience: tuple[str, ...] = ()


def extract_job_detail(
    html: str,
    page_url: str,
    *,
    selectors: DetailSelectors | None = None,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = selectors or DetailSelectors()
    defaults = defaults or {}
    ld_job = _find_job_posting(soup)

    title = _first_value(
        defaults.get("title"),
        ld_job.get("title"),
        _select_text(soup, (*selectors.title, *DEFAULT_TEXT_SELECTORS["title"])),
        _meta_content(soup, "og:title"),
    )
    company = _first_value(
        defaults.get("company"),
        _path_value(ld_job, "hiringOrganization", "name"),
        _select_text(soup, (*selectors.company, *DEFAULT_TEXT_SELECTORS["company"])),
        _meta_content(soup, "og:site_name"),
    )
    location = _first_value(
        defaults.get("location"),
        _location_from_ld(ld_job.get("jobLocation")),
        _select_text(soup, (*selectors.location, *DEFAULT_TEXT_SELECTORS["location"])),
        _path_value(ld_job, "applicantLocationRequirements", 0, "name"),
    )
    description_node = _select_node(soup, (*selectors.description, *DEFAULT_TEXT_SELECTORS["description"]))
    description_html = _first_value(
        defaults.get("description_html"),
        ld_job.get("description"),
        description_node.decode_contents() if description_node else "",
    )
    description = _first_value(
        defaults.get("description"),
        _clean_ld_html(ld_job.get("description")),
        description_node.get_text("\n", strip=True) if description_node else "",
    )
    apply_href = _select_href(soup, selectors.apply_url) if selectors.apply_url else ""
    skills = _collect_texts(soup, (*selectors.skills, *DEFAULT_TEXT_SELECTORS["skills"]))

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "description_html": description_html,
        "apply_url": _absolute_url(page_url, apply_href or defaults.get("apply_url") or ld_job.get("url") or page_url),
        "job_url": _absolute_url(page_url, defaults.get("job_url") or ld_job.get("url") or page_url),
        "job_type": _first_value(
            defaults.get("job_type"),
            ld_job.get("employmentType"),
            _select_text(soup, (*selectors.job_type, *DEFAULT_TEXT_SELECTORS["job_type"])),
        ),
        "salary_text": _first_value(
            defaults.get("salary_text"),
            _salary_from_ld(ld_job.get("baseSalary")),
            _select_text(soup, (*selectors.salary, *DEFAULT_TEXT_SELECTORS["salary"])),
        ),
        "posted_at": _first_value(
            defaults.get("posted_at"),
            ld_job.get("datePosted"),
            _select_datetime_attr(soup),
            _select_text(soup, (*selectors.posted_at, *DEFAULT_TEXT_SELECTORS["posted_at"])),
        ),
        "source_job_id": defaults.get("source_job_id") or _identifier_from_ld(ld_job.get("identifier")),
        "experience_level": _first_value(
            defaults.get("experience_level"),
            _path_value(ld_job, "experienceRequirements"),
            _select_text(soup, (*selectors.experience, *DEFAULT_TEXT_SELECTORS["experience"])),
        ),
        "skills": defaults.get("skills") or skills,
    }


def _find_job_posting(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _flatten(payload):
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return {}


def _flatten(payload: Any):
    if isinstance(payload, list):
        for item in payload:
            yield from _flatten(item)
        return
    if isinstance(payload, dict):
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from _flatten(item)
            return
        yield payload


def _select_node(soup: BeautifulSoup, selectors: tuple[str, ...]):
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node
    return None


def _select_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    node = _select_node(soup, selectors)
    if not node:
        return ""
    return node.get_text(" ", strip=True)


def _select_href(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        href = node.get("href") if node else None
        if href:
            return href
    return ""


def _collect_texts(soup: BeautifulSoup, selectors: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if text and text not in seen and len(text) <= 64:
                seen.add(text)
                values.append(text)
    return values


def _meta_content(soup: BeautifulSoup, property_name: str) -> str:
    node = soup.find("meta", attrs={"property": property_name}) or soup.find("meta", attrs={"name": property_name})
    if not node:
        return ""
    return (node.get("content") or "").strip()


def _select_datetime_attr(soup: BeautifulSoup) -> str:
    node = soup.select_one("time[datetime]")
    if not node:
        return ""
    return (node.get("datetime") or "").strip()


def _location_from_ld(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = _location_from_ld(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            return ", ".join(part for part in parts if part)
        name = value.get("name")
        if isinstance(name, str):
            return name.strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _salary_from_ld(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    currency = value.get("currency") or value.get("currencyCode") or ""
    inner = value.get("value")
    if isinstance(inner, dict):
        minimum = inner.get("minValue")
        maximum = inner.get("maxValue")
        unit = inner.get("unitText") or ""
        if minimum and maximum:
            return f"{currency} {minimum} - {maximum} {unit}".strip()
        if minimum:
            return f"{currency} {minimum} {unit}".strip()
    return ""


def _identifier_from_ld(value: Any) -> str | None:
    if isinstance(value, dict):
        candidate = value.get("value") or value.get("name")
        return str(candidate).strip() if candidate else None
    if value:
        return str(value).strip()
    return None


def _path_value(payload: Any, *path: Any) -> str:
    current = payload
    for part in path:
        if isinstance(part, int):
            if isinstance(current, list) and len(current) > part:
                current = current[part]
                continue
            return ""
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
    return current.strip() if isinstance(current, str) else ""


def _clean_ld_html(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return BeautifulSoup(value, "html.parser").get_text("\n", strip=True)


def _first_value(*values: Any) -> str:
    for value in values:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        elif value not in (None, "", [], {}):
            return str(value).strip()
    return ""


def _absolute_url(base_url: str, value: str) -> str:
    return urljoin(base_url, value or base_url)
