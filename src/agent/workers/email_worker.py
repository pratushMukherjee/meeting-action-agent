"""Email worker node for sending meeting summary emails."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_openai import ChatOpenAI

from src.agent.state import EmailResult, ErrorRecord, MeetingAgentState
from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import LLM_LATENCY, LLM_TOKENS_TOTAL, TASK_TOTAL
from src.tools.gmail import GmailAPIError, GmailClient

logger = get_logger(__name__)

EMAIL_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "email_summary.txt"


def _load_prompt() -> str:
    return EMAIL_PROMPT_PATH.read_text(encoding="utf-8")


async def _generate_email_content(
    state: MeetingAgentState,
    action_description: str,
) -> dict:
    """Use LLM to generate professional email subject and body."""
    prompt_template = _load_prompt()

    # Gather actions already taken
    actions_taken = []
    for r in state.get("jira_results", []):
        if r.success:
            actions_taken.append(f"- Created Jira ticket {r.issue_key}: {r.issue_url}")
    for r in state.get("calendar_results", []):
        if r.success:
            actions_taken.append(f"- Scheduled calendar event: {r.event_link}")

    metadata = state.get("meeting_metadata", {})
    prompt = prompt_template.format(
        meeting_title=metadata.get("meeting_title", "Meeting"),
        meeting_date=metadata.get("date", "unknown"),
        participants=", ".join(state.get("participants", [])),
        transcript=state["transcript"][:3000],  # Truncate for token limits
        actions_taken="\n".join(actions_taken) if actions_taken else "None yet",
    )

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
    )

    with LLM_LATENCY.labels(model=settings.openai_model).time():
        response = await llm.ainvoke(prompt)

    if response.usage_metadata:
        LLM_TOKENS_TOTAL.labels(model=settings.openai_model, type="input").inc(
            response.usage_metadata.get("input_tokens", 0)
        )
        LLM_TOKENS_TOTAL.labels(model=settings.openai_model, type="output").inc(
            response.usage_metadata.get("output_tokens", 0)
        )

    raw_text = str(response.content).strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "subject": f"Meeting Summary: {metadata.get('meeting_title', 'Meeting')}",
            "body": raw_text,
        }


async def email_worker(state: MeetingAgentState) -> dict:
    """LangGraph node: generate and send meeting summary emails.

    Generates email content using the LLM (referencing any Jira tickets
    or calendar events already created), then sends via Gmail API.
    """
    execution_plan = state.get("execution_plan", [])
    email_tasks = [
        task for task in execution_plan
        if task.action_item.type == "email_summary"
    ]

    if not email_tasks:
        return {"email_results": [], "current_step": "email_worker"}

    client = GmailClient()
    results: list[EmailResult] = []
    errors: list[ErrorRecord] = []

    for task in email_tasks:
        item = task.action_item
        recipients = item.recipients or state.get("participants", [])

        if not recipients:
            logger.warning(
                "no_email_recipients",
                transcript_id=state["transcript_id"],
                title=item.title,
            )
            continue

        try:
            # Generate email content via LLM
            email_content = await _generate_email_content(state, item.description)
            subject = email_content.get("subject", item.title)
            body = email_content.get("body", item.description)

            # Send email
            response = client.send_email(
                to=recipients,
                subject=subject,
                body=body,
            )

            results.append(EmailResult(
                tool_name="gmail",
                success=True,
                data=response,
                recipients=recipients,
                subject=subject,
            ))

            logger.info(
                "email_sent_successfully",
                transcript_id=state["transcript_id"],
                recipients=recipients,
                subject=subject,
            )

        except GmailAPIError as e:
            logger.error(
                "email_send_failed",
                transcript_id=state["transcript_id"],
                error=str(e),
            )
            results.append(EmailResult(
                tool_name="gmail",
                success=False,
                error=str(e),
                recipients=recipients,
                subject=item.title,
            ))
            errors.append(ErrorRecord(
                node="email_worker",
                tool_name="gmail",
                error_type="GmailAPIError",
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
        "email_results": results,
        "errors": errors,
        "current_step": "email_worker",
    }
