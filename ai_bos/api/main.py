"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_bos.api.routers import business, owner, status, webhooks
from ai_bos.logging_config import configure_logging
from ai_bos.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    yield


app = FastAPI(
    title="AI-BOS",
    description="AI Business Operating System",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(business.router, prefix="/business", tags=["business"])
app.include_router(owner.router, prefix="/owner", tags=["owner"])
app.include_router(status.router, prefix="/status", tags=["status"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
