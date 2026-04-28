import json
from collections import Counter
from pathlib import Path

from ..models import JobRecord, JobSource, ScrapeResult
from ..schemas import JobQueryParams, SourceStat, StatsResponse, TrendStat
from .deduplication import job_signatures, merge_records
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
        jobs_sorted = sorted(
            jobs,
            key=lambda item: (item.posted_at, item.quality_score, item.scraped_at),
            reverse=True,
        )
        payload = [job.model_dump(mode="json") for job in jobs_sorted]
        self.data_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def merge_jobs(self, incoming: list[JobRecord], source: JobSource) -> ScrapeResult:
        existing = self.all_jobs()
        merged = {job.id: job for job in existing}
        signature_index: dict[str, str] = {}

        for job in existing:
            for signature in job_signatures(job):
                signature_index[signature] = job.id

        inserted = 0
        updated = 0
        deduplicated = 0

        for job in incoming:
            match_id = next((signature_index[signature] for signature in job_signatures(job) if signature in signature_index), None)
            if match_id:
                deduplicated += 1
                merged_job = merge_records(merged[match_id], job)
                if merged_job != merged[match_id]:
                    updated += 1
                merged[match_id] = merged_job
                for signature in job_signatures(merged_job):
                    signature_index[signature] = match_id
                continue

            merged[job.id] = job
            inserted += 1
            for signature in job_signatures(job):
                signature_index[signature] = job.id

        self.save_jobs(list(merged.values()))
        return ScrapeResult(
            source=source,
            collected=len(incoming),
            inserted=inserted,
            updated=updated,
            deduplicated=deduplicated,
        )

    def query_jobs(self, params: JobQueryParams) -> tuple[int, list[JobRecord]]:
        items = self.all_jobs()
        if params.keyword:
            keyword = params.keyword.lower()
            items = [
                job
                for job in items
                if keyword in job.title.lower()
                or keyword in job.company.lower()
                or keyword in job.description.lower()
                or any(keyword in skill for skill in job.skills)
            ]
        if params.location:
            location = params.location.lower()
            items = [job for job in items if location in job.location.lower()]
        if params.source:
            items = [job for job in items if job.source == params.source]
        if params.company:
            company = params.company.lower()
            items = [job for job in items if company in job.company.lower()]
        if params.job_type:
            target = params.job_type.lower()
            items = [job for job in items if target in job.job_type.lower()]
        if params.workplace_type:
            items = [job for job in items if job.workplace_type == params.workplace_type]
        if params.experience_level:
            items = [job for job in items if job.experience_level == params.experience_level]
        if params.skill:
            skill = params.skill.lower()
            items = [job for job in items if any(skill in candidate for candidate in job.skills)]

        total = len(items)
        paginated = items[params.offset : params.offset + params.limit]
        return total, paginated

    def export_csv(self) -> str:
        jobs = self.all_jobs()
        header = ",".join(
            [
                "id",
                "source_job_id",
                "title",
                "company",
                "location",
                "location_city",
                "location_country",
                "workplace_type",
                "source",
                "source_website",
                "job_type",
                "experience_level",
                "salary_text",
                "job_url",
                "apply_url",
                "posted_at",
                "scraped_at",
                "skills",
            ]
        )
        rows = [
            ",".join(
                [
                    job.id,
                    _csv_escape(job.source_job_id or ""),
                    _csv_escape(job.title),
                    _csv_escape(job.company),
                    _csv_escape(job.location),
                    _csv_escape(job.location_city or ""),
                    _csv_escape(job.location_country or ""),
                    job.workplace_type.value,
                    job.source.value,
                    _csv_escape(job.source_website),
                    _csv_escape(job.job_type),
                    job.experience_level.value,
                    _csv_escape(job.salary_text or ""),
                    _csv_escape(str(job.job_url)),
                    _csv_escape(str(job.apply_url)),
                    job.posted_at.isoformat(),
                    job.scraped_at.isoformat(),
                    _csv_escape("|".join(job.skills)),
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
        skill_counts = Counter(skill for job in jobs for skill in job.skills)
        experience_counts = Counter(job.experience_level.value for job in jobs if job.experience_level.value != "unknown")
        workplace_counts = Counter(job.workplace_type.value for job in jobs if job.workplace_type.value != "unknown")

        return StatsResponse(
            total_jobs=len(jobs),
            remote_jobs=sum(1 for job in jobs if job.workplace_type.value == "remote"),
            sources=[SourceStat(source=source, jobs=count) for source, count in source_counts.most_common()],
            top_titles=[TrendStat(label=label, count=count) for label, count in title_counts.most_common(5)],
            top_skills=[TrendStat(label=label, count=count) for label, count in skill_counts.most_common(8)],
            top_companies=[TrendStat(label=label, count=count) for label, count in company_counts.most_common(5)],
            top_experience_levels=[TrendStat(label=label, count=count) for label, count in experience_counts.most_common(5)],
            top_workplace_types=[TrendStat(label=label, count=count) for label, count in workplace_counts.most_common(5)],
        )


def _csv_escape(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'
