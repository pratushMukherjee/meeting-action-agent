"""Shared test fixtures for the meeting action agent."""

from __future__ import annotations

import pytest

from src.agent.state import ActionItem, MeetingAgentState, PlannedTask


@pytest.fixture
def sample_transcript() -> str:
    return (
        "Alice: Welcome everyone to the Q1 Sprint Planning meeting. "
        "Let's start with the backlog. Bob, can you take the login bug? "
        "It's been open for two weeks now.\n\n"
        "Bob: Sure, I'll fix the login bug by Friday. It's a high priority issue.\n\n"
        "Alice: Great. We also need to schedule a follow-up meeting next Tuesday "
        "at 2pm to review the sprint progress. Charlie, can you invite the team?\n\n"
        "Charlie: Will do. Should I also send a summary of today's decisions to "
        "the stakeholders?\n\n"
        "Alice: Yes, please send a summary email to the engineering team and stakeholders. "
        "Include the action items and deadlines.\n\n"
        "Bob: One more thing - we need to create a ticket for the new dashboard feature. "
        "Medium priority, due end of month.\n\n"
        "Alice: Good call. Let's wrap up."
    )


@pytest.fixture
def sample_participants() -> list[str]:
    return ["alice@company.com", "bob@company.com", "charlie@company.com"]


@pytest.fixture
def sample_metadata() -> dict:
    return {
        "meeting_title": "Q1 Sprint Planning",
        "date": "2026-02-23",
    }


@pytest.fixture
def sample_action_items() -> list[ActionItem]:
    return [
        ActionItem(
            type="jira_ticket",
            title="Fix login bug",
            description="Fix the login bug that has been open for two weeks",
            assignee="Bob",
            priority="high",
            due_date="2026-02-27",
            confidence=0.95,
        ),
        ActionItem(
            type="jira_ticket",
            title="New dashboard feature",
            description="Create a ticket for the new dashboard feature",
            assignee=None,
            priority="medium",
            due_date="2026-02-28",
            confidence=0.85,
        ),
        ActionItem(
            type="calendar_event",
            title="Sprint Review Meeting",
            description="Review sprint progress with the team",
            attendees=["alice@company.com", "bob@company.com", "charlie@company.com"],
            meeting_time="2026-02-25T14:00:00Z",
            confidence=0.90,
        ),
        ActionItem(
            type="email_summary",
            title="Q1 Sprint Planning Summary",
            description="Summary of decisions and action items from the sprint planning meeting",
            recipients=["engineering@company.com", "stakeholders@company.com"],
            confidence=0.85,
        ),
    ]


@pytest.fixture
def sample_planned_tasks(sample_action_items: list[ActionItem]) -> list[PlannedTask]:
    return [
        PlannedTask(action_item=sample_action_items[0], order=0, can_parallel=True),
        PlannedTask(action_item=sample_action_items[1], order=1, can_parallel=True),
        PlannedTask(action_item=sample_action_items[2], order=2, can_parallel=True),
        PlannedTask(
            action_item=sample_action_items[3],
            order=3,
            depends_on=[0, 1],
            can_parallel=False,
        ),
    ]


@pytest.fixture
def sample_agent_state(
    sample_transcript: str,
    sample_participants: list[str],
    sample_metadata: dict,
) -> MeetingAgentState:
    return {
        "transcript": sample_transcript,
        "transcript_id": "test-transcript-001",
        "participants": sample_participants,
        "meeting_metadata": sample_metadata,
        "parsed_items": [],
        "execution_plan": [],
        "human_approved": False,
        "jira_results": [],
        "email_results": [],
        "calendar_results": [],
        "errors": [],
        "retry_count": 0,
        "current_step": "",
        "execution_report": None,
    }
