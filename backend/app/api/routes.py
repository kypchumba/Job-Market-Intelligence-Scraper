from fastapi import APIRouter, Depends, Query, Request, Response

from ..models import ExperienceLevel, JobSource, WorkplaceType
from ..schemas import JobQueryParams, JobsResponse, ScrapeRunResponse, StatsResponse
from ..services.dependencies import get_orchestrator, get_scrape_guard, get_store
from ..services.security import ScrapeGuard, get_client_id, verify_scrape_access


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/jobs", response_model=JobsResponse)
async def list_jobs(
    keyword: str | None = Query(default=None),
    location: str | None = Query(default=None),
    source: JobSource | None = Query(default=None),
    company: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    workplace_type: WorkplaceType | None = Query(default=None),
    experience_level: ExperienceLevel | None = Query(default=None),
    skill: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    store=Depends(get_store),
) -> JobsResponse:
    params = JobQueryParams(
        keyword=keyword,
        location=location,
        source=source,
        company=company,
        job_type=job_type,
        workplace_type=workplace_type,
        experience_level=experience_level,
        skill=skill,
        offset=offset,
        limit=limit,
    )
    total, items = store.query_jobs(params)
    return JobsResponse(total=total, offset=offset, limit=limit, items=items)


@router.post("/scrape/run", response_model=ScrapeRunResponse)
async def run_scrapers(
    request: Request,
    sources: list[JobSource] | None = Query(default=None),
    orchestrator=Depends(get_orchestrator),
    scrape_guard: ScrapeGuard = Depends(get_scrape_guard),
    _: None = Depends(verify_scrape_access),
) -> ScrapeRunResponse:
    client_id = get_client_id(request)
    await scrape_guard.enter(client_id)
    try:
        return await orchestrator.run(sources=sources)
    finally:
        scrape_guard.exit()


@router.get("/stats", response_model=StatsResponse)
async def stats(store=Depends(get_store)) -> StatsResponse:
    return store.stats()


@router.get("/export/csv")
async def export_csv(store=Depends(get_store)) -> Response:
    content = store.export_csv()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job-market-export.csv"},
    )
