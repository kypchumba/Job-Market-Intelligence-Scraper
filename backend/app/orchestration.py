import asyncio
from datetime import datetime, timezone

from .config import settings
from .models import JobRecord, JobSource, ScrapeResult
from .schemas import ScrapeRunResponse
from .scrapers.ashby_scraper import AshbyScraper
from .scrapers.brightermonday_scraper import BrighterMondayScraper
from .scrapers.careerspage_scraper import CareersPageScraper
from .scrapers.corporatestaffing_scraper import CorporateStaffingScraper
from .scrapers.fuzu_scraper import FuzuScraper
from .scrapers.greenhouse_scraper import GreenhouseScraper
from .scrapers.lever_scraper import LeverScraper
from .scrapers.myjobmag_scraper import MyJobMagScraper
from .scrapers.remoteok_scraper import RemoteOKScraper
from .scrapers.weworkremotely_scraper import WeWorkRemotelyScraper
from .services.job_store import JobStore


class ScrapeOrchestrator:
    def __init__(self, store: JobStore):
        self.store = store

    def _scraper_factories(self) -> dict[JobSource, type]:
        return {
            JobSource.remoteok: RemoteOKScraper,
            JobSource.weworkremotely: WeWorkRemotelyScraper,
            JobSource.greenhouse: GreenhouseScraper,
            JobSource.lever: LeverScraper,
            JobSource.ashby: AshbyScraper,
            JobSource.careerspage: CareersPageScraper,
            JobSource.myjobmag: MyJobMagScraper,
            JobSource.brightermonday: BrighterMondayScraper,
            JobSource.corporatestaffing: CorporateStaffingScraper,
            JobSource.fuzu: FuzuScraper,
        }

    async def run(self, sources: list[JobSource] | None = None) -> ScrapeRunResponse:
        started_at = datetime.now(timezone.utc)
        target_sources = sources or list(self._scraper_factories().keys())
        semaphore = asyncio.Semaphore(settings.scraper_concurrency)

        async def execute(source: JobSource):
            async with semaphore:
                scraper = self._scraper_factories()[source]()
                try:
                    jobs, errors = await asyncio.wait_for(
                        scraper.scrape(),
                        timeout=settings.scrape_timeout_seconds,
                    )
                    return source, jobs[: settings.max_jobs_per_source], errors
                except TimeoutError:
                    return (
                        source,
                        [],
                        [f"{source.value} scraper exceeded {settings.scrape_timeout_seconds} seconds and was stopped."],
                    )
                finally:
                    await scraper.close()

        raw_results = await asyncio.gather(*(execute(source) for source in target_sources))

        results: list[ScrapeResult] = []
        total_inserted = 0
        for source, jobs, errors in raw_results:
            result = self.store.merge_jobs(jobs, source)
            result.errors.extend(errors)
            results.append(result)
            total_inserted += result.inserted

        return ScrapeRunResponse(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            sources=results,
            total_inserted=total_inserted,
        )
