"""Jira worker node for creating tickets from action items."""

from __future__ import annotations

from src.agent.state import ErrorRecord, JiraResult, MeetingAgentState
from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import TASK_TOTAL
from src.tools.jira import JiraAPIError, JiraClient

logger = get_logger(__name__)


async def jira_worker(state: MeetingAgentState) -> dict:
    """LangGraph node: create Jira tickets for action items.

    Processes all jira_ticket action items from the execution plan,
    creates issues via the Jira REST API, and returns results.
    """
    execution_plan = state.get("execution_plan", [])
    jira_tasks = [
        task for task in execution_plan
        if task.action_item.type == "jira_ticket"
    ]

    if not jira_tasks:
        return {"jira_results": [], "current_step": "jira_worker"}

    client = JiraClient()
    results: list[JiraResult] = []
    errors: list[ErrorRecord] = []

    try:
        for task in jira_tasks:
            item = task.action_item

            try:
                response = await client.create_issue(
                    project_key=settings.jira_default_project,
                    summary=item.title,
                    description=item.description,
                    assignee=item.assignee,
                    priority=item.priority,
                    labels=["meeting-action-agent"],
                )

                results.append(JiraResult(
                    tool_name="jira",
                    success=True,
                    data=response,
                    issue_key=response["key"],
                    issue_url=response["url"],
                ))

                logger.info(
                    "jira_ticket_created",
                    transcript_id=state["transcript_id"],
                    issue_key=response["key"],
                    title=item.title,
                )

            except JiraAPIError as e:
                logger.error(
                    "jira_ticket_failed",
                    transcript_id=state["transcript_id"],
                    title=item.title,
                    error=str(e),
                )
                results.append(JiraResult(
                    tool_name="jira",
                    success=False,
                    error=str(e),
                ))
                errors.append(ErrorRecord(
                    node="jira_worker",
                    tool_name="jira",
                    error_type="JiraAPIError",
                    message=str(e),
                    retryable=e.retryable,
                ))
    finally:
        await client.close()

    successful = sum(1 for r in results if r.success)
    if successful == len(results):
        TASK_TOTAL.labels(status="success").inc()
    elif successful > 0:
        TASK_TOTAL.labels(status="partial").inc()
    else:
        TASK_TOTAL.labels(status="failure").inc()

    return {
        "jira_results": results,
        "errors": errors,
        "current_step": "jira_worker",
    }
