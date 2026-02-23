"""Pydantic schemas for action API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActionResponse(BaseModel):
    """Response for a single action record."""

    id: str
    action_type: str
    title: str
    description: str | None = None
    status: str
    result: dict | None = None
    error_message: str | None = None
    confidence: float | None = None
    execution_time_ms: int | None = None
    created_at: datetime | None = None


class ActionsListResponse(BaseModel):
    """Response for listing all actions for a transcript."""

    transcript_id: str
    actions: list[ActionResponse]
    total: int
    successful: int
    failed: int
