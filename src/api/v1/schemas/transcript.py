"""Pydantic schemas for transcript API requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptSubmitRequest(BaseModel):
    """Request body for submitting a transcript for processing."""

    transcript: str = Field(..., min_length=10, max_length=100000)
    meeting_id: str | None = None
    participants: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class TranscriptSubmitResponse(BaseModel):
    """Response after submitting a transcript."""

    transcript_id: str
    status: str = "processing"
    message: str = "Transcript submitted for processing"


class TranscriptStatusResponse(BaseModel):
    """Response for transcript processing status."""

    transcript_id: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    execution_plan: list[dict] | None = None
    execution_report: dict | None = None


class ApprovalRequest(BaseModel):
    """Request body for approving/editing an execution plan."""

    approved: bool = True
    edited_plan: list[dict] | None = None
    feedback: str | None = None


class ApprovalResponse(BaseModel):
    """Response after submitting approval."""

    transcript_id: str
    status: str
    message: str
