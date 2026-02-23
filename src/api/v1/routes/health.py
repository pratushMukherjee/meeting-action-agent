"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Basic health check."""
    return {"status": "healthy", "service": "meeting-action-agent"}


@router.get("/health/ready")
async def readiness_check() -> dict:
    """Readiness check — verifies dependencies are available."""
    checks = {
        "api": "ok",
    }
    # In production, add DB and Redis connectivity checks here
    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
    }
