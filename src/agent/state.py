"""LangGraph agent state schema and data models."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field


# --- Data Models ---

class ActionItem(BaseModel):
    """A single action item extracted from a meeting transcript."""

    type: Literal["jira_ticket", "email_summary", "calendar_event"]
    title: str
    description: str
    assignee: str | None = None
    priority: str | None = None  # high, medium, low
    due_date: str | None = None  # ISO date
    recipients: list[str] | None = None
    attendees: list[str] | None = None
    meeting_time: str | None = None  # ISO datetime
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PlannedTask(BaseModel):
    """A planned task in the execution plan."""

    action_item: ActionItem
    order: int
    depends_on: list[int] = Field(default_factory=list)
    can_parallel: bool = False


class ToolResult(BaseModel):
    """Result from a tool execution."""

    tool_name: str
    success: bool
    data: dict = Field(default_factory=dict)
    error: str | None = None


class JiraResult(ToolResult):
    """Result from Jira ticket creation."""

    issue_key: str = ""
    issue_url: str = ""


class EmailResult(ToolResult):
    """Result from email sending."""

    recipients: list[str] = Field(default_factory=list)
    subject: str = ""


class CalendarResult(ToolResult):
    """Result from calendar event creation."""

    event_id: str = ""
    event_link: str = ""


class ErrorRecord(BaseModel):
    """Record of an error during execution."""

    node: str
    tool_name: str | None = None
    error_type: str
    message: str
    retryable: bool = False


class ExecutionReport(BaseModel):
    """Final execution report aggregating all results."""

    transcript_id: str
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    jira_tickets: list[dict] = Field(default_factory=list)
    emails_sent: list[dict] = Field(default_factory=list)
    events_created: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    execution_time_ms: int = 0


# --- LangGraph State ---

class MeetingAgentState(TypedDict):
    """State schema for the LangGraph meeting action agent.

    Fields using `Annotated[list, operator.add]` are append-only —
    each node returns new items which are appended to the existing list.
    """

    # Input
    transcript: str
    transcript_id: str
    participants: list[str]
    meeting_metadata: dict

    # Parsing
    parsed_items: list[ActionItem]

    # Planning
    execution_plan: list[PlannedTask]
    human_approved: bool

    # Execution results (append-only via reducer)
    jira_results: Annotated[list[JiraResult], operator.add]
    email_results: Annotated[list[EmailResult], operator.add]
    calendar_results: Annotated[list[CalendarResult], operator.add]
    errors: Annotated[list[ErrorRecord], operator.add]

    # Control flow
    retry_count: int
    current_step: str

    # Final output
    execution_report: ExecutionReport | None
