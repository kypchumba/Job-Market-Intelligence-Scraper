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


class JobRecord(BaseModel):
    id: str
    title: str
    company: str
    location: str = "Remote"
    source: JobSource
    source_type: str = "scraped"
    job_type: str = "unknown"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    apply_url: HttpUrl | str
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    salary_text: str | None = None


class ScrapeResult(BaseModel):
    source: JobSource
    collected: int
    inserted: int
    deduplicated: int
    errors: list[str] = Field(default_factory=list)
