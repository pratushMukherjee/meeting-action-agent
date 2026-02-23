"""Unit tests for transcript parsing node."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.nodes.parse_transcript import parse_transcript
from src.agent.state import MeetingAgentState


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response with action items."""
    items = [
        {
            "type": "jira_ticket",
            "title": "Fix login bug",
            "description": "Fix the login bug by Friday",
            "assignee": "Bob",
            "priority": "high",
            "due_date": "2026-02-27",
            "confidence": 0.95,
        },
        {
            "type": "calendar_event",
            "title": "Sprint Review Meeting",
            "description": "Review sprint progress",
            "attendees": ["alice@company.com", "bob@company.com"],
            "meeting_time": "2026-02-25T14:00:00Z",
            "confidence": 0.90,
        },
        {
            "type": "email_summary",
            "title": "Meeting Summary",
            "description": "Summary of decisions",
            "recipients": ["stakeholders@company.com"],
            "confidence": 0.85,
        },
    ]

    mock_response = MagicMock()
    mock_response.content = json.dumps(items)
    mock_response.usage_metadata = {"input_tokens": 500, "output_tokens": 200}
    return mock_response


@pytest.mark.asyncio
async def test_parse_transcript_extracts_items(
    sample_agent_state: MeetingAgentState,
    mock_llm_response,
):
    """Test that parse_transcript extracts action items from transcript."""
    with patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_llm_response
        mock_llm_class.return_value = mock_llm

        result = await parse_transcript(sample_agent_state)

        assert "parsed_items" in result
        assert len(result["parsed_items"]) == 3
        assert result["parsed_items"][0].type == "jira_ticket"
        assert result["parsed_items"][0].title == "Fix login bug"
        assert result["parsed_items"][1].type == "calendar_event"
        assert result["parsed_items"][2].type == "email_summary"


@pytest.mark.asyncio
async def test_parse_transcript_handles_empty_response(
    sample_agent_state: MeetingAgentState,
):
    """Test handling when LLM returns empty list."""
    mock_response = MagicMock()
    mock_response.content = "[]"
    mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 5}

    with patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = await parse_transcript(sample_agent_state)

        assert result["parsed_items"] == []


@pytest.mark.asyncio
async def test_parse_transcript_handles_invalid_json(
    sample_agent_state: MeetingAgentState,
):
    """Test handling when LLM returns invalid JSON."""
    mock_response = MagicMock()
    mock_response.content = "This is not JSON"
    mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 10}

    with patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = await parse_transcript(sample_agent_state)

        assert result["parsed_items"] == []


@pytest.mark.asyncio
async def test_parse_transcript_handles_markdown_fenced_json(
    sample_agent_state: MeetingAgentState,
):
    """Test handling when LLM wraps JSON in markdown code fences."""
    items = [
        {
            "type": "jira_ticket",
            "title": "Test ticket",
            "description": "Test desc",
            "confidence": 0.9,
        }
    ]
    mock_response = MagicMock()
    mock_response.content = f"```json\n{json.dumps(items)}\n```"
    mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

    with patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = await parse_transcript(sample_agent_state)

        assert len(result["parsed_items"]) == 1
        assert result["parsed_items"][0].title == "Test ticket"


@pytest.mark.asyncio
async def test_parse_transcript_skips_invalid_items(
    sample_agent_state: MeetingAgentState,
):
    """Test that invalid action items are skipped without failing."""
    items = [
        {
            "type": "jira_ticket",
            "title": "Valid ticket",
            "description": "Valid desc",
            "confidence": 0.9,
        },
        {
            "type": "invalid_type",  # Invalid type
            "title": "Bad item",
            "description": "This should be skipped",
        },
    ]
    mock_response = MagicMock()
    mock_response.content = json.dumps(items)
    mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

    with patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = await parse_transcript(sample_agent_state)

        assert len(result["parsed_items"]) == 1
        assert result["parsed_items"][0].title == "Valid ticket"
