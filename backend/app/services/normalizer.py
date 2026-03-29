import hashlib
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ..models import JobRecord, JobSource


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_tags(tags: list[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags or []:
        cleaned = normalize_whitespace(tag).lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized


def job_fingerprint(title: str, company: str, apply_url: str) -> str:
    payload = f"{normalize_whitespace(title).lower()}|{normalize_whitespace(company).lower()}|{apply_url.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clean_html_text(value: str) -> str:
    if not value:
        return ""

    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "img", "svg"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True).replace("\xa0", " ")
    text = re.sub(r"\s*•\s*", " • ", text)
    return normalize_whitespace(text)


def clean_job_text_fields(
    title: str,
    company: str,
    description: str,
    source: JobSource,
) -> tuple[str, str, str]:
    cleaned_title = clean_html_text(title)
    cleaned_company = clean_html_text(company)
    cleaned_description = clean_html_text(description)

    if source == JobSource.weworkremotely and cleaned_company.lower() == "unknown company":
        prefix, separator, suffix = cleaned_title.partition(":")
        if separator and prefix and suffix:
            cleaned_company = normalize_whitespace(prefix)
            cleaned_title = normalize_whitespace(suffix)

    return cleaned_title, cleaned_company, cleaned_description


def clean_loaded_job(job: JobRecord) -> JobRecord:
    title, company, description = clean_job_text_fields(
        title=job.title,
        company=job.company,
        description=job.description,
        source=job.source,
    )
    return job.model_copy(
        update={
            "title": title,
            "company": company,
            "location": clean_html_text(job.location) or "Remote",
            "description": description,
            "job_type": normalize_whitespace(job.job_type).lower(),
            "tags": normalize_tags(job.tags),
        }
    )


def normalize_job(payload: dict, source: JobSource) -> JobRecord:
    posted_at = payload.get("posted_at") or datetime.now(timezone.utc)
    if isinstance(posted_at, str):
        posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))

    title, company, description = clean_job_text_fields(
        title=payload["title"],
        company=payload["company"],
        description=payload.get("description", ""),
        source=source,
    )

    return JobRecord(
        id=job_fingerprint(title, company, payload["apply_url"]),
        title=title,
        company=company,
        location=clean_html_text(payload.get("location", "Remote")) or "Remote",
        source=source,
        source_type=payload.get("source_type", "scraped"),
        job_type=normalize_whitespace(payload.get("job_type", "unknown")).lower(),
        description=description,
        tags=normalize_tags(payload.get("tags")),
        apply_url=payload["apply_url"],
        posted_at=posted_at,
        salary_text=payload.get("salary_text"),
    )
