"""Calendar worker node for scheduling follow-up meetings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.agent.state import CalendarResult, ErrorRecord, MeetingAgentState
from src.core.logging import get_logger
from src.core.metrics import TASK_TOTAL
from src.tools.calendar import CalendarAPIError, CalendarClient

logger = get_logger(__name__)

MAX_DAYS_AHEAD = 30
MAX_ATTENDEES = 50


async def calendar_worker(state: MeetingAgentState) -> dict:
    """LangGraph node: create calendar events for follow-up meetings.

    Processes all calendar_event action items from the execution plan,
    checks for conflicts, and creates events via Google Calendar API.
    """
    execution_plan = state.get("execution_plan", [])
    calendar_tasks = [
        task for task in execution_plan
        if task.action_item.type == "calendar_event"
    ]

    if not calendar_tasks:
        return {"calendar_results": [], "current_step": "calendar_worker"}

    client = CalendarClient()
    results: list[CalendarResult] = []
    errors: list[ErrorRecord] = []

    for task in calendar_tasks:
        item = task.action_item
        attendees = item.attendees or []

        # Guardrail: max attendees
        if len(attendees) > MAX_ATTENDEES:
            logger.warning(
                "too_many_attendees",
                transcript_id=state["transcript_id"],
                count=len(attendees),
            )
            attendees = attendees[:MAX_ATTENDEES]

        # Parse or default the meeting time
        start_time = item.meeting_time
        if not start_time:
            # Default to tomorrow at 10am UTC
            tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
            start_time = tomorrow.replace(hour=10, minute=0, second=0).isoformat()

        # Guardrail: max scheduling horizon
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            max_date = datetime.now(timezone.utc) + timedelta(days=MAX_DAYS_AHEAD)
            if start_dt > max_date:
                error_msg = f"Cannot schedule more than {MAX_DAYS_AHEAD} days ahead"
                logger.warning(
                    "event_too_far_ahead",
                    transcript_id=state["transcript_id"],
                    requested_date=start_time,
                )
                errors.append(ErrorRecord(
                    node="calendar_worker",
                    tool_name="calendar",
                    error_type="ValidationError",
                    message=error_msg,
                ))
                results.append(CalendarResult(
                    tool_name="calendar",
                    success=False,
                    error=error_msg,
                ))
                continue
        except ValueError:
            pass  # Let the Calendar API handle invalid dates

        try:
            # Check for conflicts
            end_time_dt = datetime.fromisoformat(
                start_time.replace("Z", "+00:00")
            ) + timedelta(hours=1)
            end_time = end_time_dt.isoformat()

            conflicts = client.check_conflicts(start_time, end_time)
            if conflicts:
                conflict_names = [e.get("summary", "Unknown") for e in conflicts]
                logger.warning(
                    "calendar_conflicts_found",
                    transcript_id=state["transcript_id"],
                    conflicts=conflict_names,
                )

            # Create the event
            response = client.create_event(
                summary=item.title,
                start_time=start_time,
                end_time=end_time,
                attendees=attendees,
                description=item.description,
            )

            results.append(CalendarResult(
                tool_name="calendar",
                success=True,
                data=response,
                event_id=response["id"],
                event_link=response["htmlLink"],
            ))

            logger.info(
                "calendar_event_created",
                transcript_id=state["transcript_id"],
                event_id=response["id"],
                title=item.title,
            )

        except CalendarAPIError as e:
            logger.error(
                "calendar_event_failed",
                transcript_id=state["transcript_id"],
                error=str(e),
            )
            results.append(CalendarResult(
                tool_name="calendar",
                success=False,
                error=str(e),
            ))
            errors.append(ErrorRecord(
                node="calendar_worker",
                tool_name="calendar",
                error_type="CalendarAPIError",
                message=str(e),
                retryable=e.retryable,
            ))

    successful = sum(1 for r in results if r.success)
    if successful == len(results) and results:
        TASK_TOTAL.labels(status="success").inc()
    elif successful > 0:
        TASK_TOTAL.labels(status="partial").inc()
    elif results:
        TASK_TOTAL.labels(status="failure").inc()

    return {
        "calendar_results": results,
        "errors": errors,
        "current_step": "calendar_worker",
    }
