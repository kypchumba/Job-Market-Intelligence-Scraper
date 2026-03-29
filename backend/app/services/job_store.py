import json
from collections import Counter
from pathlib import Path

from ..models import JobRecord, JobSource, ScrapeResult
from ..schemas import JobQueryParams, SourceStat, StatsResponse, TrendStat
from .normalizer import clean_loaded_job


class JobStore:
    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self.data_file.write_text("[]", encoding="utf-8")

    def all_jobs(self) -> list[JobRecord]:
        raw = json.loads(self.data_file.read_text(encoding="utf-8"))
        return [clean_loaded_job(JobRecord.model_validate(item)) for item in raw]

    def save_jobs(self, jobs: list[JobRecord]) -> None:
        jobs_sorted = sorted(jobs, key=lambda item: item.posted_at, reverse=True)
        payload = [job.model_dump(mode="json") for job in jobs_sorted]
        self.data_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def merge_jobs(self, incoming: list[JobRecord], source: JobSource) -> ScrapeResult:
        existing = self.all_jobs()
        merged = {job.id: job for job in existing}
        inserted = 0
        deduplicated = 0

        for job in incoming:
            if job.id in merged:
                deduplicated += 1
                continue
            merged[job.id] = job
            inserted += 1

        self.save_jobs(list(merged.values()))
        return ScrapeResult(
            source=source,
            collected=len(incoming),
            inserted=inserted,
            deduplicated=deduplicated,
        )

    def query_jobs(self, params: JobQueryParams) -> list[JobRecord]:
        items = self.all_jobs()
        if params.keyword:
            keyword = params.keyword.lower()
            items = [
                job
                for job in items
                if keyword in job.title.lower()
                or keyword in job.company.lower()
                or keyword in job.description.lower()
                or any(keyword in tag for tag in job.tags)
            ]
        if params.location:
            location = params.location.lower()
            items = [job for job in items if location in job.location.lower()]
        if params.source:
            items = [job for job in items if job.source == params.source]
        if params.job_type:
            target = params.job_type.lower()
            items = [job for job in items if target in job.job_type.lower()]
        return items[: params.limit]

    def export_csv(self) -> str:
        jobs = self.all_jobs()
        header = "id,title,company,location,source,job_type,apply_url,posted_at,tags"
        rows = [
            ",".join(
                [
                    job.id,
                    _csv_escape(job.title),
                    _csv_escape(job.company),
                    _csv_escape(job.location),
                    job.source.value,
                    _csv_escape(job.job_type),
                    _csv_escape(str(job.apply_url)),
                    job.posted_at.isoformat(),
                    _csv_escape("|".join(job.tags)),
                ]
            )
            for job in jobs
        ]
        return "\n".join([header, *rows])

    def stats(self) -> StatsResponse:
        jobs = self.all_jobs()
        source_counts = Counter(job.source.value for job in jobs)
        title_counts = Counter(job.title for job in jobs)
        company_counts = Counter(job.company for job in jobs)
        skill_counts = Counter(tag for job in jobs for tag in job.tags)

        return StatsResponse(
            total_jobs=len(jobs),
            remote_jobs=sum(1 for job in jobs if "remote" in job.location.lower()),
            sources=[SourceStat(source=source, jobs=count) for source, count in source_counts.most_common()],
            top_titles=[TrendStat(label=label, count=count) for label, count in title_counts.most_common(5)],
            top_skills=[TrendStat(label=label, count=count) for label, count in skill_counts.most_common(8)],
            top_companies=[TrendStat(label=label, count=count) for label, count in company_counts.most_common(5)],
        )


def _csv_escape(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'
