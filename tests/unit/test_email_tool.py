"""Unit tests for Gmail tool wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.tools.gmail import GmailAPIError, GmailClient


@pytest.fixture
def gmail_client():
    client = GmailClient(
        credentials_file="test_creds.json",
        token_file="test_token.json",
    )
    return client


def test_send_email_success(gmail_client):
    """Test successful email sending."""
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.return_value = {
        "id": "msg_123",
        "threadId": "thread_456",
    }

    gmail_client._service = mock_service

    result = gmail_client.send_email(
        to=["alice@company.com"],
        subject="Meeting Summary",
        body="<p>Here are the key decisions...</p>",
    )

    assert result["id"] == "msg_123"
    assert result["recipients"] == ["alice@company.com"]
    assert result["subject"] == "Meeting Summary"


def test_send_email_with_cc(gmail_client):
    """Test email sending with CC recipients."""
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.return_value = {
        "id": "msg_456",
        "threadId": "thread_789",
    }

    gmail_client._service = mock_service

    result = gmail_client.send_email(
        to=["alice@company.com"],
        subject="Summary",
        body="Body text",
        cc=["bob@company.com"],
    )

    assert result["id"] == "msg_456"


def test_send_email_failure(gmail_client):
    """Test email send failure raises GmailAPIError."""
    mock_service = MagicMock()
    mock_service.users().messages().send().execute.side_effect = Exception("API error")

    gmail_client._service = mock_service

    with pytest.raises(GmailAPIError):
        gmail_client.send_email(
            to=["alice@company.com"],
            subject="Test",
            body="Test body",
        )
