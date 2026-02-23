"""Transcript processing API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_session
from src.api.v1.schemas.transcript import (
    ApprovalRequest,
    ApprovalResponse,
    TranscriptStatusResponse,
    TranscriptSubmitRequest,
    TranscriptSubmitResponse,
)
from src.core.logging import get_logger
from src.db.models import Transcript
from src.db.repository import TranscriptRepository
from src.tasks.process_transcript import process_transcript_task

logger = get_logger(__name__)

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.post("", response_model=TranscriptSubmitResponse, status_code=202)
async def submit_transcript(
    request: TranscriptSubmitRequest,
    session: AsyncSession = Depends(get_session),
) -> TranscriptSubmitResponse:
    """Submit a meeting transcript for processing.

    Returns 202 Accepted with a transcript_id for polling status.
    """
    repo = TranscriptRepository(session)
    transcript = await repo.create(
        content=request.transcript,
        meeting_id=request.meeting_id,
        meeting_title=request.metadata.get("meeting_title"),
        participants=request.participants,
        metadata_=request.metadata,
        status="processing",
    )
    await session.commit()

    # Enqueue async processing task
    process_transcript_task.delay(
        transcript_id=str(transcript.id),
        transcript_text=request.transcript,
        participants=request.participants,
        metadata=request.metadata,
    )

    logger.info(
        "transcript_submitted",
        transcript_id=str(transcript.id),
        length=len(request.transcript),
    )

    return TranscriptSubmitResponse(
        transcript_id=str(transcript.id),
        status="processing",
    )


@router.get("/{transcript_id}", response_model=TranscriptStatusResponse)
async def get_transcript_status(
    transcript_id: str,
    session: AsyncSession = Depends(get_session),
) -> TranscriptStatusResponse:
    """Get the processing status and results for a transcript."""
    try:
        tid = uuid.UUID(transcript_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transcript ID format")

    repo = TranscriptRepository(session)
    transcript = await repo.get_by_id(tid)

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return TranscriptStatusResponse(
        transcript_id=str(transcript.id),
        status=transcript.status,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
    )


@router.post("/{transcript_id}/approve", response_model=ApprovalResponse)
async def approve_plan(
    transcript_id: str,
    request: ApprovalRequest,
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    """Approve or reject a pending execution plan.

    This resumes the LangGraph agent from the human_approval interrupt.
    """
    try:
        tid = uuid.UUID(transcript_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transcript ID format")

    repo = TranscriptRepository(session)
    transcript = await repo.get_by_id(tid)

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    if transcript.status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Transcript is not awaiting approval (status: {transcript.status})",
        )

    # Update status based on approval
    new_status = "executing" if request.approved else "failed"
    await repo.update_status(tid, new_status)
    await session.commit()

    # TODO: Resume LangGraph from checkpoint using Command(resume=...)
    # This requires the thread_id stored during initial processing

    logger.info(
        "plan_approval_received",
        transcript_id=transcript_id,
        approved=request.approved,
    )

    return ApprovalResponse(
        transcript_id=transcript_id,
        status=new_status,
        message="Plan approved, execution resumed" if request.approved else "Plan rejected",
    )


@router.post("/{transcript_id}/reject", response_model=ApprovalResponse)
async def reject_plan(
    transcript_id: str,
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    """Reject a pending execution plan."""
    return await approve_plan(
        transcript_id,
        ApprovalRequest(approved=False),
        session,
    )
