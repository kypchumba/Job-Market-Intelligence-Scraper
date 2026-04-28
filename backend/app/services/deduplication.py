from __future__ import annotations

from typing import Iterable

from ..models import JobRecord
from .normalizer import canonicalize_url, completeness_score, normalize_whitespace


def job_signatures(job: JobRecord) -> list[str]:
    signatures: list[str] = []

    if job.source_job_id:
        signatures.append(f"source-id:{job.source.value}:{job.source_job_id.lower()}")

    canonical_url = canonicalize_url(str(job.canonical_url or job.job_url or job.apply_url))
    if canonical_url:
        signatures.append(f"url:{canonical_url.lower()}")

    title = normalize_whitespace(job.title).lower()
    company = normalize_whitespace(job.company).lower()
    city = normalize_whitespace(job.location_city or "")
    country = normalize_whitespace(job.location_country or "")
    job_type = normalize_whitespace(job.job_type or "")
    if title and company:
        signatures.append(f"content:{title}|{company}|{city.lower()}|{country.lower()}|{job_type.lower()}")

    return signatures


def merge_records(existing: JobRecord, incoming: JobRecord) -> JobRecord:
    primary, secondary = _ordered_records(existing, incoming)

    merged_sections = primary.description_sections or secondary.description_sections
    merged_skills = _unique(primary.skills, secondary.skills, primary.tags, secondary.tags)
    merged_sources = _unique(primary.aggregated_sources, secondary.aggregated_sources, [primary.source.value], [secondary.source.value])

    update = {
        "source_job_id": _pick(primary.source_job_id, secondary.source_job_id),
        "title": _pick(primary.title, secondary.title),
        "company": _pick(primary.company, secondary.company),
        "location": _pick(primary.location, secondary.location),
        "location_city": _pick(primary.location_city, secondary.location_city),
        "location_region": _pick(primary.location_region, secondary.location_region),
        "location_country": _pick(primary.location_country, secondary.location_country),
        "workplace_type": _pick(primary.workplace_type, secondary.workplace_type),
        "source_type": _pick(primary.source_type, secondary.source_type),
        "source_website": _pick(primary.source_website, secondary.source_website),
        "aggregated_sources": merged_sources,
        "job_type": _pick(primary.job_type, secondary.job_type),
        "experience_level": _pick(primary.experience_level, secondary.experience_level),
        "description": _pick(primary.description, secondary.description),
        "description_html": _pick(primary.description_html, secondary.description_html),
        "description_sections": merged_sections,
        "skills": merged_skills,
        "tags": merged_skills,
        "job_url": _pick(str(primary.job_url), str(secondary.job_url)),
        "apply_url": _pick(str(primary.apply_url), str(secondary.apply_url)),
        "canonical_url": _pick(str(primary.canonical_url), str(secondary.canonical_url)),
        "posted_at": min(primary.posted_at, secondary.posted_at),
        "scraped_at": max(primary.scraped_at, secondary.scraped_at),
        "discovered_at": min(primary.discovered_at, secondary.discovered_at),
        "salary_text": _pick(primary.salary_text, secondary.salary_text),
        "salary_min": primary.salary_min if primary.salary_min is not None else secondary.salary_min,
        "salary_max": primary.salary_max if primary.salary_max is not None else secondary.salary_max,
        "salary_currency": _pick(primary.salary_currency, secondary.salary_currency),
        "salary_interval": _pick(primary.salary_interval, secondary.salary_interval),
    }

    merged = primary.model_copy(update=update)
    return merged.model_copy(update={"quality_score": completeness_score(merged)})


def _ordered_records(left: JobRecord, right: JobRecord) -> tuple[JobRecord, JobRecord]:
    left_score = completeness_score(left)
    right_score = completeness_score(right)
    if right_score > left_score:
        return right, left
    return left, right


def _pick(primary, secondary):
    if primary not in (None, "", [], {}, "unknown"):
        return primary
    return secondary


def _unique(*groups: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for group in groups:
        for item in group or []:
            cleaned = normalize_whitespace(str(item)).lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                values.append(cleaned)
    return values
