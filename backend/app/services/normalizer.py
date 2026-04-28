from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from ..models import DescriptionSection, ExperienceLevel, JobRecord, JobSource, WorkplaceType


NOISE_PHRASES = (
    "advertise your job here",
    "upload your cv",
    "free cv review",
    "job alert",
    "subscribe to job alert",
    "sign in and apply",
    "log in and apply",
    "view all latest jobs today",
    "lorem ipsum",
)

JOB_TYPE_PATTERNS = (
    (r"\bfull[\s-]?time\b", "full-time"),
    (r"\bpart[\s-]?time\b", "part-time"),
    (r"\bintern(ship)?\b", "internship"),
    (r"\bcontract\b", "contract"),
    (r"\btemporary\b", "temporary"),
    (r"\bfreelance\b", "freelance"),
    (r"\bconsult(ing|ant)\b", "contract"),
    (r"\bvolunteer\b", "volunteer"),
)

EXPERIENCE_KEYWORDS = {
    "internship": ("internship", "intern", "graduate trainee"),
    "entry": ("entry level", "entry-level", "entry", "no experience"),
    "junior": ("junior", "associate"),
    "mid": ("mid level", "mid-level", "intermediate"),
    "senior": ("senior", "sr."),
    "lead": ("lead", "manager", "head of", "staff"),
    "principal": ("principal", "architect"),
    "executive": ("executive", "director", "vp", "vice president", "chief"),
}

WORKPLACE_PATTERNS = {
    WorkplaceType.remote: ("remote", "work from home", "home-based", "distributed", "worldwide"),
    WorkplaceType.hybrid: ("hybrid", "part remote", "flexible workplace"),
    WorkplaceType.onsite: ("onsite", "on-site", "office based", "office-based", "in office"),
}

COUNTRY_BY_CITY = {
    "nairobi": "Kenya",
    "mombasa": "Kenya",
    "kisumu": "Kenya",
    "nakuru": "Kenya",
    "eldoret": "Kenya",
    "kiambu": "Kenya",
    "kampala": "Uganda",
    "gulu": "Uganda",
    "lagos": "Nigeria",
    "abuja": "Nigeria",
    "accra": "Ghana",
    "london": "United Kingdom",
    "dublin": "Ireland",
    "new york": "USA",
    "nyc": "USA",
    "san francisco": "USA",
    "sf": "USA",
}

SKILL_ALIASES = {
    "python": ("python",),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "javascript": ("javascript", " js "),
    "typescript": ("typescript",),
    "react": ("react", "react.js"),
    "next.js": ("next.js", "nextjs"),
    "node.js": ("node.js", " node "),
    "java": (" java ",),
    "kotlin": ("kotlin",),
    "swift": ("swift",),
    "golang": ("golang", " go "),
    "c#": ("c#", ".net", "asp.net"),
    "sql": (" sql ", "postgres", "postgresql", "mysql", "sql server"),
    "excel": ("excel", "microsoft excel"),
    "powerpoint": ("powerpoint", "microsoft powerpoint"),
    "word": ("microsoft word",),
    "machine learning": ("machine learning", " ml "),
    "data analysis": ("data analysis", "data analytics", "analyze data"),
    "data visualization": ("data visualization", "visualization"),
    "computer vision": ("computer vision",),
    "nlp": ("natural language processing", " nlp "),
    "aws": (" aws ", "amazon web services"),
    "azure": (" azure ",),
    "gcp": (" gcp ", "google cloud"),
    "docker": (" docker ",),
    "kubernetes": ("kubernetes", " k8s "),
    "terraform": ("terraform",),
    "devops": ("devops", "site reliability", " sre "),
    "git": (" git ",),
    "linux": (" linux ",),
    "customer service": ("customer service", "customer support"),
    "billing": ("billing",),
    "collections": ("collections", "debt collection"),
    "sales": (" sales ",),
    "marketing": ("marketing", "digital marketing"),
    "project management": ("project management",),
    "account management": ("account management",),
    "recruitment": ("recruitment", "talent acquisition", "hiring"),
    "communication": ("communication skills", "written communication", "verbal communication"),
    "leadership": ("leadership", "team leadership"),
    "compliance": ("compliance",),
    "quality assurance": ("quality assurance", " qa "),
    "customer experience": ("customer experience",),
    "office administration": ("office administration", "administration"),
    "bookkeeping": ("bookkeeping",),
}


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_tags(tags: list[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags or []:
        cleaned = normalize_whitespace(clean_html_text(str(tag))).lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            normalized.append(cleaned)
    return normalized


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=False)
    keep = {
        key: values
        for key, values in query.items()
        if key.lower() in {"gh_jid", "jid", "jobid", "job_id", "opening", "vacancy"}
    }
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or parsed.path,
            "",
            urlencode(keep, doseq=True),
            "",
        )
    )


def extract_source_job_id(url: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("gh_jid", "jid", "jobid", "job_id", "opening", "vacancy"):
        values = query.get(key)
        if values and values[0]:
            return values[0].strip()

    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        return None

    last = path_parts[-1]
    slug_match = re.search(r"([a-z0-9]{6,})$", last.lower())
    if slug_match:
        return slug_match.group(1)
    return last or None


def job_fingerprint(
    title: str,
    company: str,
    canonical_url: str,
    source_job_id: str | None,
    location: str,
) -> str:
    payload = "|".join(
        [
            normalize_whitespace(title).lower(),
            normalize_whitespace(company).lower(),
            normalize_whitespace(location).lower(),
            (source_job_id or "").lower(),
            canonical_url.lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clean_html_text(value: str) -> str:
    if not value:
        return ""

    soup = BeautifulSoup(unescape(value), "html.parser")
    for tag in soup(["script", "style", "img", "svg", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True).replace("\xa0", " ")
    text = text.replace("â€¢", "•")
    text = re.sub(r"\s*[•·]\s*", " • ", text)
    return normalize_whitespace(text)


def normalize_job_type(value: str | None, title: str = "", description: str = "") -> str:
    text = clean_html_text(" ".join(part for part in [value or "", title, description] if part)).lower()
    for pattern, label in JOB_TYPE_PATTERNS:
        if re.search(pattern, text):
            return label
    return "unknown"


def normalize_experience_level(value: str | None) -> ExperienceLevel:
    text = normalize_whitespace(clean_html_text(value or "")).lower()
    if not text:
        return ExperienceLevel.unknown
    for label, keywords in EXPERIENCE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return ExperienceLevel(label)
    return ExperienceLevel.unknown


def infer_experience_level(title: str, description: str) -> ExperienceLevel:
    text = f"{title} {description}".lower()
    explicit = normalize_experience_level(text)
    if explicit != ExperienceLevel.unknown:
        return explicit

    years_match = re.search(r"(\d+)\+?\s+years?", text)
    if years_match:
        years = int(years_match.group(1))
        if years <= 1:
            return ExperienceLevel.entry
        if years <= 3:
            return ExperienceLevel.junior
        if years <= 5:
            return ExperienceLevel.mid
        if years <= 8:
            return ExperienceLevel.senior
        return ExperienceLevel.lead
    return ExperienceLevel.unknown


def parse_datetime(value, *, fallback: datetime | None = None) -> datetime:
    fallback = fallback or datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 1_000_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if not value:
        return fallback

    text = normalize_whitespace(clean_html_text(str(value)))
    lowered = text.lower()
    if lowered == "today":
        return fallback
    if lowered == "yesterday":
        return fallback - timedelta(days=1)

    relative = re.search(r"(\d+)\s+(day|days|week|weeks|month|months)\s+ago", lowered)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        multiplier = 30 if "month" in unit else 7 if "week" in unit else 1
        return fallback - timedelta(days=amount * multiplier)

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%b %d, %Y %H:%M:%S %z",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return fallback


def normalize_company_name(value: str, *, fallback_url: str = "") -> str:
    cleaned = clean_html_text(value)
    if cleaned and cleaned.lower() not in {"unknown company", "company"}:
        return cleaned
    hostname = urlparse(fallback_url).hostname or ""
    if hostname:
        return hostname.replace("www.", "").split(".")[0].replace("-", " ").title()
    return "Unknown company"


def infer_workplace_type(location: str, title: str = "", description: str = "") -> WorkplaceType:
    text = clean_html_text(" ".join(part for part in [location, title, description] if part)).lower()
    for workplace_type, keywords in WORKPLACE_PATTERNS.items():
        if any(keyword in text for keyword in keywords):
            return workplace_type
    if location and location.lower() in {"kenya", "uganda", "nigeria", "africa"}:
        return WorkplaceType.unknown
    return WorkplaceType.onsite if location else WorkplaceType.unknown


def parse_location(value: str | None, title: str = "", description: str = "") -> dict[str, str | WorkplaceType | None]:
    raw = normalize_whitespace(clean_html_text(value or ""))
    workplace_type = infer_workplace_type(raw, title, description)

    if workplace_type == WorkplaceType.remote and raw.lower() in {"", "remote", "worldwide", "global"}:
        return {
            "location": "Remote",
            "location_city": None,
            "location_region": None,
            "location_country": None,
            "workplace_type": workplace_type,
        }

    sanitized = raw.replace("•", ", ").replace("/", ", ").replace("  ", " ").strip(" ,")
    tokens = [normalize_whitespace(part) for part in re.split(r",|\|", sanitized) if normalize_whitespace(part)]

    city = None
    region = None
    country = None
    for token in tokens:
        lowered = token.lower()
        if lowered in COUNTRY_BY_CITY:
            city = token.title()
            country = COUNTRY_BY_CITY[lowered]
            continue
        if lowered in {"kenya", "uganda", "nigeria", "ghana", "usa", "united states", "ireland", "united kingdom"}:
            country = token.title()
            continue
        if not region and len(token) <= 32:
            region = token.title()

    if not city:
        city_match = re.search(
            r"\b(nairobi|mombasa|kisumu|nakuru|eldoret|kampala|gulu|lagos|abuja|accra|london|dublin|san francisco|new york|nyc|sf)\b",
            sanitized,
            re.IGNORECASE,
        )
        if city_match:
            raw_city = city_match.group(1)
            normalized_city = {"nyc": "New York", "sf": "San Francisco"}.get(raw_city.lower(), raw_city.title())
            city = normalized_city
            country = country or COUNTRY_BY_CITY.get(raw_city.lower())

    location_text = sanitized or ("Remote" if workplace_type == WorkplaceType.remote else "Unspecified")
    if workplace_type == WorkplaceType.hybrid and "hybrid" not in location_text.lower():
        location_text = f"{location_text} (Hybrid)".strip()

    return {
        "location": location_text,
        "location_city": city,
        "location_region": region if region != city else None,
        "location_country": country,
        "workplace_type": workplace_type,
    }


def parse_salary(value: str | int | float | None, title: str = "", description: str = "") -> dict[str, str | float | None]:
    if isinstance(value, (int, float)):
        return {
            "salary_text": str(value),
            "salary_min": float(value),
            "salary_max": None,
            "salary_currency": None,
            "salary_interval": None,
        }

    combined = clean_html_text(" ".join(part for part in [str(value or ""), title, description[:300]] if part))
    if not combined or "confidential" in combined.lower():
        return {
            "salary_text": None,
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "salary_interval": None,
        }

    currency_match = re.search(r"(KSh|KES|\$|USD|EUR|€|GBP|£)", combined, re.IGNORECASE)
    currency = _normalize_currency(currency_match.group(1)) if currency_match else None
    interval_match = re.search(r"\b(hour|day|week|month|year|annum)\b", combined, re.IGNORECASE)
    interval = interval_match.group(1).lower() if interval_match else None

    range_match = re.search(
        r"(?P<min>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix1>[Kk])?\s*(?:-|to|–)\s*(?P<max>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix2>[Kk])?",
        combined,
    )
    if range_match:
        salary_min = _expand_number(range_match.group("min"), range_match.group("suffix1"))
        salary_max = _expand_number(range_match.group("max"), range_match.group("suffix2"))
        salary_text = normalize_whitespace(range_match.group(0))
        return {
            "salary_text": salary_text,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_currency": currency,
            "salary_interval": interval,
        }

    single_match = re.search(r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<suffix>[Kk])?", combined)
    if single_match and currency:
        salary_value = _expand_number(single_match.group("value"), single_match.group("suffix"))
        return {
            "salary_text": normalize_whitespace(single_match.group(0)),
            "salary_min": salary_value,
            "salary_max": salary_value,
            "salary_currency": currency,
            "salary_interval": interval,
        }

    return {
        "salary_text": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": currency,
        "salary_interval": interval,
    }


def extract_skills(title: str, company: str, description: str, raw_tags: list[str] | None = None) -> list[str]:
    text = clean_html_text(" ".join([title, company, description]))
    lowered = f" {text.lower()} "
    extracted: list[str] = []

    for skill, aliases in SKILL_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            extracted.append(skill)

    for tag in normalize_tags(raw_tags):
        extracted.append(tag)

    phrase_matches = re.findall(
        r"(?:experience with|experience in|knowledge of|proficiency in|familiarity with)\s+([a-z0-9+/#\-\s]{3,60})",
        lowered,
    )
    for match in phrase_matches:
        fragment = re.split(r"[.;:,]| and | or ", match, maxsplit=1)[0]
        candidate = normalize_whitespace(fragment)
        if 2 <= len(candidate.split()) <= 4:
            extracted.append(candidate)

    return normalize_tags(extracted)[:20]


def structure_description(value: str) -> list[DescriptionSection]:
    if not value:
        return []

    soup = BeautifulSoup(unescape(value), "html.parser")
    text = soup.get_text("\n", strip=True) if "<" in value else value
    lines = [normalize_whitespace(line) for line in text.splitlines() if normalize_whitespace(line)]
    if not lines:
        return []

    sections: list[DescriptionSection] = []
    current_heading = "Overview"
    current_items: list[str] = []

    def flush():
        nonlocal current_heading, current_items
        if current_items:
            sections.append(DescriptionSection(heading=current_heading, items=current_items[:20]))
        current_heading = "Overview"
        current_items = []

    for line in lines:
        heading = _normalize_heading(line)
        if heading:
            flush()
            current_heading = heading
            continue

        cleaned = re.sub(r"^[•*\-\d.\)\(]+\s*", "", line).strip()
        if cleaned and cleaned.lower() not in {current_heading.lower(), "description"}:
            current_items.append(cleaned)

    flush()

    if not sections:
        sentences = [item.strip() for item in re.split(r"(?<=\.)\s+", clean_html_text(value)) if item.strip()]
        return [DescriptionSection(heading="Overview", items=sentences[:8])]
    return sections


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


def looks_like_job(payload: dict) -> bool:
    title = clean_html_text(str(payload.get("title", ""))).lower()
    description = clean_html_text(str(payload.get("description", ""))).lower()
    combined = f"{title} {description}"
    if not title or len(title) < 4:
        return False
    if any(phrase in combined for phrase in NOISE_PHRASES):
        return False
    return True


def completeness_score(job: JobRecord) -> int:
    score = 0
    fields = [
        bool(job.title),
        bool(job.company and job.company.lower() != "unknown company"),
        bool(job.location and job.location.lower() not in {"unspecified", "africa", "kenya"}),
        bool(job.description),
        bool(job.posted_at),
        bool(job.job_url),
        job.job_type != "unknown",
        job.experience_level != ExperienceLevel.unknown,
        bool(job.salary_text or job.salary_min or job.salary_max),
        bool(job.skills),
        bool(job.source_website),
        bool(job.source_job_id),
        bool(job.scraped_at),
    ]
    score += sum(1 for field in fields if field)
    score += min(len(job.description_sections), 4)
    score += min(len(job.skills), 5)
    return score


def clean_loaded_job(job: JobRecord) -> JobRecord:
    payload = job.model_dump(mode="json")
    payload.setdefault("skills", payload.get("tags", []))
    payload.setdefault("job_url", payload.get("apply_url"))
    payload.setdefault("canonical_url", payload.get("apply_url"))
    payload.setdefault("source_website", job.source_website or urlparse(str(job.apply_url)).netloc)
    payload.setdefault("aggregated_sources", job.aggregated_sources or [job.source.value])
    payload.setdefault("scraped_at", payload.get("discovered_at") or payload.get("scraped_at"))
    return normalize_job(payload, job.source)


def normalize_job(payload: dict, source: JobSource) -> JobRecord:
    now = datetime.now(timezone.utc)
    raw_title = payload.get("title") or "Unknown role"
    raw_job_url = str(payload.get("job_url") or payload.get("apply_url") or payload.get("url") or "")
    raw_apply_url = str(payload.get("apply_url") or raw_job_url or "")
    canonical_url = canonicalize_url(raw_job_url or raw_apply_url) or raw_job_url or raw_apply_url
    source_job_id = normalize_whitespace(str(payload.get("source_job_id") or extract_source_job_id(canonical_url) or ""))
    title, company, description = clean_job_text_fields(
        title=raw_title,
        company=normalize_company_name(payload.get("company", ""), fallback_url=canonical_url),
        description=payload.get("description_text") or payload.get("description", ""),
        source=source,
    )

    location_info = parse_location(payload.get("location"), title, description)
    salary_info = parse_salary(payload.get("salary_text"), title, description)
    experience_level = normalize_experience_level(payload.get("experience_level"))
    if experience_level == ExperienceLevel.unknown:
        experience_level = infer_experience_level(title, description)

    raw_html = str(payload.get("description_html") or payload.get("description") or "")
    description_sections = structure_description(raw_html or description)
    skills = extract_skills(title, company, description, payload.get("skills") or payload.get("tags"))
    job_type = normalize_job_type(payload.get("job_type"), title, description)
    source_website = normalize_whitespace(
        str(payload.get("source_website") or urlparse(canonical_url or raw_apply_url).netloc or source.value)
    )
    posted_at = parse_datetime(payload.get("posted_at"), fallback=now)
    scraped_at = parse_datetime(payload.get("scraped_at") or payload.get("discovered_at"), fallback=now)
    discovered_at = parse_datetime(payload.get("discovered_at") or payload.get("scraped_at"), fallback=scraped_at)
    aggregated_sources = normalize_tags(payload.get("aggregated_sources") or [source.value])

    record = JobRecord(
        id=job_fingerprint(title, company, canonical_url, source_job_id or None, location_info["location"] or ""),
        source_job_id=source_job_id or None,
        title=title,
        company=company,
        location=location_info["location"] or "Remote",
        location_city=location_info["location_city"],
        location_region=location_info["location_region"],
        location_country=location_info["location_country"],
        workplace_type=location_info["workplace_type"] or WorkplaceType.unknown,
        source=source,
        source_type=payload.get("source_type", "scraped"),
        source_website=source_website,
        aggregated_sources=aggregated_sources,
        job_type=job_type,
        experience_level=experience_level,
        description=description,
        description_html=raw_html,
        description_sections=description_sections,
        skills=skills,
        tags=skills,
        job_url=raw_job_url or raw_apply_url,
        apply_url=raw_apply_url or raw_job_url,
        canonical_url=canonical_url or raw_apply_url or raw_job_url,
        posted_at=posted_at,
        scraped_at=scraped_at,
        discovered_at=discovered_at,
        salary_text=salary_info["salary_text"],
        salary_min=salary_info["salary_min"],
        salary_max=salary_info["salary_max"],
        salary_currency=salary_info["salary_currency"],
        salary_interval=salary_info["salary_interval"],
    )
    return record.model_copy(update={"quality_score": completeness_score(record)})


def _normalize_currency(value: str) -> str:
    mapping = {
        "ksh": "KES",
        "kes": "KES",
        "$": "USD",
        "usd": "USD",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
    }
    return mapping.get(value.lower(), value.upper())


def _expand_number(value: str, suffix: str | None) -> float:
    numeric = float(value.replace(",", ""))
    if suffix and suffix.lower() == "k":
        numeric *= 1000
    return numeric


def _normalize_heading(value: str) -> str | None:
    cleaned = normalize_whitespace(value.strip(": "))
    lowered = cleaned.lower()
    known = {
        "description": "Overview",
        "job summary": "Overview",
        "about the job": "Overview",
        "responsibilities": "Responsibilities",
        "key responsibilities": "Responsibilities",
        "duties": "Responsibilities",
        "what you'll do": "Responsibilities",
        "requirements": "Requirements",
        "qualifications": "Requirements",
        "qualifications & requirements": "Requirements",
        "experience": "Requirements",
        "benefits": "Benefits",
        "what's on offer": "Benefits",
        "method of application": "Application",
    }
    if lowered in known:
        return known[lowered]
    if len(cleaned) <= 48 and cleaned == cleaned.title() and cleaned.lower() not in {"remote", "onsite"}:
        return cleaned
    return None
