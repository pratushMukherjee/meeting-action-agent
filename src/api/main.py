"""FastAPI application factory and lifespan management."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from src.api.v1.routes import actions, health, transcripts
from src.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    setup_logging()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Meeting Action Agent API",
        description="AI agent that processes meeting transcripts and executes follow-up actions",
        version="0.1.0",
        lifespan=lifespan,
    )

    # API routes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(transcripts.router, prefix="/api/v1")
    app.include_router(actions.router, prefix="/api/v1")

    # Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


app = create_app()
