from functools import lru_cache

from ..config import settings
from ..orchestration import ScrapeOrchestrator
from .job_store import JobStore
from .security import ScrapeGuard


@lru_cache
def get_store() -> JobStore:
    return JobStore(settings.data_file)


@lru_cache
def get_orchestrator() -> ScrapeOrchestrator:
    return ScrapeOrchestrator(get_store())


@lru_cache
def get_scrape_guard() -> ScrapeGuard:
    return ScrapeGuard()
