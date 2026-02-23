"""Integration tests for the full LangGraph agent execution."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.graph import build_graph
from src.agent.state import MeetingAgentState


@pytest.fixture
def mock_openai_responses():
    """Mock LLM responses for the full pipeline."""
    # parse_transcript response
    parse_response = MagicMock()
    parse_response.content = json.dumps([
        {
            "type": "jira_ticket",
            "title": "Fix login bug",
            "description": "Fix the login bug by Friday",
            "assignee": "Bob",
            "priority": "high",
            "confidence": 0.95,
        },
    ])
    parse_response.usage_metadata = {"input_tokens": 500, "output_tokens": 200}

    return [parse_response]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_graph_with_no_items(sample_agent_state: MeetingAgentState):
    """Test graph handles transcripts with no action items gracefully."""
    parse_response = MagicMock()
    parse_response.content = "[]"
    parse_response.usage_metadata = {"input_tokens": 100, "output_tokens": 5}

    with patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_llm_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = parse_response
        mock_llm_class.return_value = mock_llm

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-001"}}

        result = await graph.ainvoke(sample_agent_state, config)

        assert result["execution_report"] is not None
        assert result["execution_report"].total_actions == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_graph_parse_and_plan(sample_agent_state: MeetingAgentState):
    """Test that parsing and planning nodes execute correctly."""
    parse_response = MagicMock()
    parse_response.content = json.dumps([
        {
            "type": "jira_ticket",
            "title": "Test ticket",
            "description": "Test description",
            "assignee": "Alice",
            "priority": "medium",
            "confidence": 0.9,
        },
    ])
    parse_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

    # Auto-approve for testing
    sample_agent_state["human_approved"] = True

    with (
        patch("src.agent.nodes.parse_transcript.ChatOpenAI") as mock_parse_llm,
        patch("src.agent.workers.jira_worker.JiraClient") as mock_jira_class,
    ):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = parse_response
        mock_parse_llm.return_value = mock_llm

        mock_jira = AsyncMock()
        mock_jira.create_issue.return_value = {
            "key": "MEET-1",
            "id": "10001",
            "url": "https://test.atlassian.net/browse/MEET-1",
        }
        mock_jira_class.return_value = mock_jira

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-002"}}

        result = await graph.ainvoke(sample_agent_state, config)

        assert len(result["parsed_items"]) == 1
        assert result["parsed_items"][0].type == "jira_ticket"
