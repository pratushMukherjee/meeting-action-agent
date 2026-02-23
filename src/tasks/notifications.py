"""Celery tasks for sending status update notifications."""

from __future__ import annotations

from src.core.logging import get_logger
from src.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="send_status_notification")
def send_status_notification(
    transcript_id: str,
    status: str,
    details: dict | None = None,
) -> dict:
    """Send a status notification for transcript processing.

    Can be extended to send notifications via webhook, WebSocket, or email.
    """
    logger.info(
        "status_notification_sent",
        transcript_id=transcript_id,
        status=status,
    )

    # Placeholder: integrate with webhook/WebSocket for real-time notifications
    return {
        "transcript_id": transcript_id,
        "status": status,
        "notified": True,
    }
