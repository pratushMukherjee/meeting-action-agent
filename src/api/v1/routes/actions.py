"""Action status query routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_session
from src.api.v1.schemas.action import ActionResponse, ActionsListResponse
from src.db.repository import ActionRepository

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("/{transcript_id}", response_model=ActionsListResponse)
async def get_actions(
    transcript_id: str,
    session: AsyncSession = Depends(get_session),
) -> ActionsListResponse:
    """Get all actions for a specific transcript."""
    try:
        tid = uuid.UUID(transcript_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid transcript ID format")

    repo = ActionRepository(session)
    actions = await repo.get_by_transcript(tid)

    action_responses = [
        ActionResponse(
            id=str(a.id),
            action_type=a.action_type,
            title=a.title,
            description=a.description,
            status=a.status,
            result=a.result,
            error_message=a.error_message,
            confidence=a.confidence,
            execution_time_ms=a.execution_time_ms,
            created_at=a.created_at,
        )
        for a in actions
    ]

    successful = sum(1 for a in actions if a.status == "completed")
    failed = sum(1 for a in actions if a.status == "failed")

    return ActionsListResponse(
        transcript_id=transcript_id,
        actions=action_responses,
        total=len(actions),
        successful=successful,
        failed=failed,
    )
