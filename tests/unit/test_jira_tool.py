"""Unit tests for Jira tool wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tools.jira import JiraAPIError, JiraClient


@pytest.fixture
def jira_client():
    return JiraClient(
        server_url="https://test.atlassian.net",
        user_email="test@company.com",
        api_token="test-token",
    )


@pytest.mark.asyncio
async def test_create_issue_success(jira_client):
    """Test successful Jira issue creation."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "key": "MEET-123",
        "id": "10001",
        "self": "https://test.atlassian.net/rest/api/3/issue/10001",
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.is_closed = False

    jira_client._client = mock_client

    result = await jira_client.create_issue(
        project_key="MEET",
        summary="Fix login bug",
        description="The login page throws a 500 error",
        assignee="Bob",
        priority="high",
    )

    assert result["key"] == "MEET-123"
    assert "url" in result
    assert "MEET-123" in result["url"]


@pytest.mark.asyncio
async def test_create_issue_bad_request(jira_client):
    """Test Jira 400 error raises non-retryable JiraAPIError immediately."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid project key"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.is_closed = False

    jira_client._client = mock_client

    with pytest.raises(JiraAPIError) as exc_info:
        await jira_client.create_issue(
            project_key="INVALID",
            summary="Test",
            description="Test desc",
        )

    assert not exc_info.value.retryable
    assert exc_info.value.status_code == 400
    # Should only be called once (no retries for non-retryable errors)
    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_create_issue_server_error_retries(jira_client):
    """Test Jira 500 error triggers retries then raises."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.is_closed = False

    jira_client._client = mock_client

    with pytest.raises(JiraAPIError) as exc_info:
        await jira_client.create_issue(
            project_key="MEET",
            summary="Test",
            description="Test desc",
        )

    assert exc_info.value.retryable
    assert exc_info.value.status_code == 500
    # Should have retried 3 times
    assert mock_client.post.call_count == 3


@pytest.mark.asyncio
async def test_close_client(jira_client):
    """Test client cleanup."""
    mock_client = AsyncMock()
    mock_client.is_closed = False
    jira_client._client = mock_client

    await jira_client.close()
    mock_client.aclose.assert_called_once()
