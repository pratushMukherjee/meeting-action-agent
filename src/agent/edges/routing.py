"""Conditional edge routing functions for the agent graph."""

from __future__ import annotations

from typing import Literal

from langgraph.types import Send

from src.agent.state import MeetingAgentState


def route_after_approval(
    state: MeetingAgentState,
) -> list[Send] | str:
    """Route to appropriate workers after human approval.

    If approved, fans out to workers based on action types in the plan.
    If rejected or no plan, routes to synthesize (which generates an empty report).
    """
    if not state.get("human_approved", False):
        return "synthesize"

    execution_plan = state.get("execution_plan", [])
    if not execution_plan:
        return "synthesize"

    # Determine which worker types are needed
    action_types = {task.action_item.type for task in execution_plan}

    # Fan out to workers in parallel using Send API
    destinations: list[Send] = []

    if "jira_ticket" in action_types:
        destinations.append(Send("jira_worker", state))
    if "calendar_event" in action_types:
        destinations.append(Send("calendar_worker", state))

    # Email goes after jira/calendar if they exist, otherwise parallel
    if "email_summary" in action_types:
        if not destinations:
            destinations.append(Send("email_worker", state))
        else:
            # Email will be routed separately after jira/calendar complete
            destinations.append(Send("email_worker", state))

    if not destinations:
        return "synthesize"

    return destinations


def route_after_parsing(
    state: MeetingAgentState,
) -> Literal["plan_actions", "synthesize"]:
    """Route after transcript parsing.

    If no action items were found, skip directly to synthesize.
    Otherwise, proceed to action planning.
    """
    parsed_items = state.get("parsed_items", [])
    if not parsed_items:
        return "synthesize"
    return "plan_actions"


def should_continue_or_end(
    state: MeetingAgentState,
) -> Literal["synthesize"]:
    """After workers complete, always route to synthesize."""
    return "synthesize"
