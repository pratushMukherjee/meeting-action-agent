"""Tool access policies: allowlists, parameter validation, scope limits."""

from __future__ import annotations

from src.core.config import settings
from src.core.exceptions import GuardrailViolation
from src.core.logging import get_logger
from src.core.metrics import GUARDRAIL_VIOLATIONS

logger = get_logger(__name__)

# Tool allowlists per worker role
WORKER_TOOL_ALLOWLIST: dict[str, set[str]] = {
    "jira_worker": {"jira"},
    "email_worker": {"gmail"},
    "calendar_worker": {"calendar"},
}

# Action scope: only CREATE operations allowed
ALLOWED_OPERATIONS = {"create_issue", "send_email", "create_event"}

# Parameter limits
MAX_EMAIL_RECIPIENTS = 20
MAX_CALENDAR_ATTENDEES = 50
MAX_JIRA_SUMMARY_LENGTH = 255
MAX_JIRA_DESCRIPTION_LENGTH = 32000


def check_tool_access(worker_name: str, tool_name: str) -> None:
    """Verify a worker is allowed to use a specific tool.

    Raises GuardrailViolation if the tool is not in the worker's allowlist.
    """
    allowed_tools = WORKER_TOOL_ALLOWLIST.get(worker_name, set())
    if tool_name not in allowed_tools:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="unauthorized_tool_access").inc()
        raise GuardrailViolation(
            "tool_access",
            f"Worker '{worker_name}' is not allowed to use tool '{tool_name}'",
        )


def validate_email_params(
    recipients: list[str],
    subject: str,
    body: str,
) -> None:
    """Validate email parameters before sending."""
    # Recipient count limit
    if len(recipients) > MAX_EMAIL_RECIPIENTS:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="too_many_recipients").inc()
        raise GuardrailViolation(
            "email_params",
            f"Too many recipients ({len(recipients)}, max {MAX_EMAIL_RECIPIENTS})",
        )

    # Domain allowlist
    allowed_domains = settings.allowed_domains_list
    for email in recipients:
        domain = email.split("@")[-1] if "@" in email else ""
        if domain and domain not in allowed_domains:
            GUARDRAIL_VIOLATIONS.labels(guardrail_type="blocked_email_domain").inc()
            raise GuardrailViolation(
                "email_params",
                f"Email domain '{domain}' is not in the allowed list",
            )

    if not subject.strip():
        raise GuardrailViolation("email_params", "Email subject cannot be empty")


def validate_jira_params(
    project_key: str,
    summary: str,
    description: str,
) -> None:
    """Validate Jira ticket parameters before creation."""
    if len(summary) > MAX_JIRA_SUMMARY_LENGTH:
        raise GuardrailViolation(
            "jira_params",
            f"Summary too long ({len(summary)} chars, max {MAX_JIRA_SUMMARY_LENGTH})",
        )

    if len(description) > MAX_JIRA_DESCRIPTION_LENGTH:
        raise GuardrailViolation(
            "jira_params",
            f"Description too long ({len(description)} chars, max {MAX_JIRA_DESCRIPTION_LENGTH})",
        )

    if not project_key.strip():
        raise GuardrailViolation("jira_params", "Project key cannot be empty")


def validate_calendar_params(
    attendees: list[str],
    start_time: str,
) -> None:
    """Validate calendar event parameters before creation."""
    if len(attendees) > MAX_CALENDAR_ATTENDEES:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="too_many_attendees").inc()
        raise GuardrailViolation(
            "calendar_params",
            f"Too many attendees ({len(attendees)}, max {MAX_CALENDAR_ATTENDEES})",
        )

    if not start_time.strip():
        raise GuardrailViolation("calendar_params", "Start time cannot be empty")
