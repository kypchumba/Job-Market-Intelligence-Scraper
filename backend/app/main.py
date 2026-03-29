from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import settings
from .services.dependencies import get_orchestrator


@asynccontextmanager
async def lifespan(_: FastAPI):
    orchestrator = get_orchestrator()
    if not orchestrator.store.all_jobs():
        await orchestrator.run(sources=None)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
