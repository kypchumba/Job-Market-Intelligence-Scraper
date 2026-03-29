from datetime import datetime

from pydantic import BaseModel, Field

from .models import JobRecord, JobSource, ScrapeResult


class JobQueryParams(BaseModel):
    keyword: str | None = None
    location: str | None = None
    source: JobSource | None = None
    job_type: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


class JobsResponse(BaseModel):
    total: int
    items: list[JobRecord]


class ScrapeRunResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    sources: list[ScrapeResult]
    total_inserted: int


class SourceStat(BaseModel):
    source: str
    jobs: int


class TrendStat(BaseModel):
    label: str
    count: int


class StatsResponse(BaseModel):
    total_jobs: int
    remote_jobs: int
    sources: list[SourceStat]
    top_titles: list[TrendStat]
    top_skills: list[TrendStat]
    top_companies: list[TrendStat]
