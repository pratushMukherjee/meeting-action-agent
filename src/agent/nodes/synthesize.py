"""Synthesize execution results into a final report."""

from __future__ import annotations

from src.agent.state import ExecutionReport, MeetingAgentState
from src.core.logging import get_logger

logger = get_logger(__name__)


async def synthesize(state: MeetingAgentState) -> dict:
    """LangGraph node: aggregate all worker results into a final execution report.

    Collects results from Jira, Email, and Calendar workers and produces
    a structured ExecutionReport.
    """
    jira_results = state.get("jira_results", [])
    email_results = state.get("email_results", [])
    calendar_results = state.get("calendar_results", [])
    errors = state.get("errors", [])

    total = len(jira_results) + len(email_results) + len(calendar_results)
    successful = sum(1 for r in jira_results if r.success)
    successful += sum(1 for r in email_results if r.success)
    successful += sum(1 for r in calendar_results if r.success)

    report = ExecutionReport(
        transcript_id=state["transcript_id"],
        total_actions=total,
        successful_actions=successful,
        failed_actions=total - successful,
        jira_tickets=[
            {
                "key": r.issue_key,
                "url": r.issue_url,
                "status": "created" if r.success else "failed",
                "error": r.error,
            }
            for r in jira_results
        ],
        emails_sent=[
            {
                "recipients": r.recipients,
                "subject": r.subject,
                "status": "sent" if r.success else "failed",
                "error": r.error,
            }
            for r in email_results
        ],
        events_created=[
            {
                "event_id": r.event_id,
                "link": r.event_link,
                "status": "created" if r.success else "failed",
                "error": r.error,
            }
            for r in calendar_results
        ],
        errors=[
            {
                "node": e.node,
                "tool": e.tool_name,
                "type": e.error_type,
                "message": e.message,
            }
            for e in errors
        ],
    )

    logger.info(
        "execution_report_generated",
        transcript_id=state["transcript_id"],
        total_actions=report.total_actions,
        successful=report.successful_actions,
        failed=report.failed_actions,
    )

    return {
        "execution_report": report,
        "current_step": "synthesize",
    }
