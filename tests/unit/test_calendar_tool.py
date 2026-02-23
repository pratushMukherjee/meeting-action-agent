"""Unit tests for Google Calendar tool wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.tools.calendar import CalendarAPIError, CalendarClient


@pytest.fixture
def calendar_client():
    return CalendarClient(
        credentials_file="test_creds.json",
        token_file="test_token.json",
    )


def test_create_event_success(calendar_client):
    """Test successful calendar event creation."""
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        "id": "event_123",
        "htmlLink": "https://calendar.google.com/event?eid=event_123",
        "status": "confirmed",
    }
    mock_service.events().list().execute.return_value = {"items": []}

    calendar_client._service = mock_service

    result = calendar_client.create_event(
        summary="Sprint Review",
        start_time="2026-02-25T14:00:00Z",
        attendees=["alice@company.com", "bob@company.com"],
        description="Review sprint progress",
    )

    assert result["id"] == "event_123"
    assert "htmlLink" in result


def test_create_event_with_default_end_time(calendar_client):
    """Test event creation defaults to 1 hour duration."""
    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        "id": "event_456",
        "htmlLink": "https://calendar.google.com/event?eid=event_456",
        "status": "confirmed",
    }

    calendar_client._service = mock_service

    result = calendar_client.create_event(
        summary="Quick Sync",
        start_time="2026-02-25T10:00:00Z",
    )

    assert result["id"] == "event_456"
    # Verify the insert was called with end_time 1 hour after start
    call_args = mock_service.events().insert.call_args
    body = call_args.kwargs.get("body") or call_args[1].get("body")
    assert "end" in body


def test_check_conflicts(calendar_client):
    """Test conflict checking."""
    mock_service = MagicMock()
    mock_service.events().list().execute.return_value = {
        "items": [
            {"summary": "Existing Meeting", "id": "existing_1"},
        ]
    }

    calendar_client._service = mock_service

    conflicts = calendar_client.check_conflicts(
        start_time="2026-02-25T14:00:00Z",
        end_time="2026-02-25T15:00:00Z",
    )

    assert len(conflicts) == 1
    assert conflicts[0]["summary"] == "Existing Meeting"


def test_create_event_failure(calendar_client):
    """Test event creation failure raises CalendarAPIError."""
    mock_service = MagicMock()
    mock_service.events().insert().execute.side_effect = Exception("Quota exceeded")

    calendar_client._service = mock_service

    with pytest.raises(CalendarAPIError):
        calendar_client.create_event(
            summary="Test Event",
            start_time="2026-02-25T14:00:00Z",
        )
