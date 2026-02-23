"""Celery task for processing transcripts through the agent graph."""

from __future__ import annotations

import asyncio
import time
import uuid

from src.core.logging import get_logger
from src.core.metrics import ACTIVE_SESSIONS, TASK_DURATION, TASK_TOTAL
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


def _run_agent(
    transcript_id: str,
    transcript_text: str,
    participants: list[str],
    metadata: dict,
) -> dict:
    """Run the LangGraph agent synchronously (called from Celery)."""
    from src.agent.graph import build_graph

    graph = build_graph()

    initial_state = {
        "transcript": transcript_text,
        "transcript_id": transcript_id,
        "participants": participants,
        "meeting_metadata": metadata,
        "parsed_items": [],
        "execution_plan": [],
        "human_approved": True,  # Auto-approve for async processing
        "jira_results": [],
        "email_results": [],
        "calendar_results": [],
        "errors": [],
        "retry_count": 0,
        "current_step": "",
        "execution_report": None,
    }

    config = {"configurable": {"thread_id": transcript_id}}

    # Run the async graph in a new event loop
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(graph.ainvoke(initial_state, config))
    finally:
        loop.close()

    # Extract execution report
    report = result.get("execution_report")
    if report:
        return report.model_dump()
    return {"transcript_id": transcript_id, "status": "completed", "errors": []}


@celery_app.task(
    name="process_transcript",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def process_transcript_task(
    self,
    transcript_id: str,
    transcript_text: str,
    participants: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Celery task: process a meeting transcript through the agent pipeline.

    This task:
    1. Runs the LangGraph agent graph
    2. Tracks metrics (duration, success/failure)
    3. Updates the transcript status in the database
    4. Returns the execution report
    """
    participants = participants or []
    metadata = metadata or {}

    logger.info(
        "processing_transcript_started",
        transcript_id=transcript_id,
        task_id=self.request.id,
    )

    ACTIVE_SESSIONS.inc()
    start_time = time.time()

    try:
        result = _run_agent(transcript_id, transcript_text, participants, metadata)
        TASK_TOTAL.labels(status="success").inc()

        logger.info(
            "processing_transcript_completed",
            transcript_id=transcript_id,
            total_actions=result.get("total_actions", 0),
            successful=result.get("successful_actions", 0),
        )
        return result

    except Exception as exc:
        TASK_TOTAL.labels(status="failure").inc()
        logger.error(
            "processing_transcript_failed",
            transcript_id=transcript_id,
            error=str(exc),
        )

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)

        return {
            "transcript_id": transcript_id,
            "status": "failed",
            "error": str(exc),
        }

    finally:
        duration = time.time() - start_time
        TASK_DURATION.observe(duration)
        ACTIVE_SESSIONS.dec()
