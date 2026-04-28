from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class JobSource(str, Enum):
    remoteok = "remoteok"
    weworkremotely = "weworkremotely"
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    careerspage = "careerspage"
    myjobmag = "myjobmag"
    brightermonday = "brightermonday"
    corporatestaffing = "corporatestaffing"
    fuzu = "fuzu"


class WorkplaceType(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    unknown = "unknown"


class ExperienceLevel(str, Enum):
    internship = "internship"
    entry = "entry"
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"
    principal = "principal"
    executive = "executive"
    unknown = "unknown"


class DescriptionSection(BaseModel):
    heading: str
    items: list[str] = Field(default_factory=list)


class JobRecord(BaseModel):
    id: str
    source_job_id: str | None = None
    title: str
    company: str
    location: str = "Remote"
    location_city: str | None = None
    location_region: str | None = None
    location_country: str | None = None
    workplace_type: WorkplaceType = WorkplaceType.unknown
    source: JobSource
    source_type: str = "scraped"
    source_website: str = ""
    aggregated_sources: list[str] = Field(default_factory=list)
    job_type: str = "unknown"
    experience_level: ExperienceLevel = ExperienceLevel.unknown
    description: str = ""
    description_html: str = ""
    description_sections: list[DescriptionSection] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    job_url: HttpUrl | str = ""
    apply_url: HttpUrl | str = ""
    canonical_url: HttpUrl | str = ""
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    quality_score: int = 0


class ScrapeResult(BaseModel):
    source: JobSource
    collected: int
    inserted: int
    updated: int = 0
    deduplicated: int
    errors: list[str] = Field(default_factory=list)
