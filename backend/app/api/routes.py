from fastapi import APIRouter, Depends, Query, Request, Response

from ..models import JobSource
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
    job_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    store=Depends(get_store),
) -> JobsResponse:
    params = JobQueryParams(
        keyword=keyword,
        location=location,
        source=source,
        job_type=job_type,
        limit=limit,
    )
    items = store.query_jobs(params)
    return JobsResponse(total=len(items), items=items)


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
