"""Integration tests for FastAPI API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_session
from src.api.main import create_app


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    app = create_app()
    return TestClient(app)


def test_health_check(client):
    """Test basic health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "meeting-action-agent"


def test_readiness_check(client):
    """Test readiness check endpoint."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "not_ready")


def test_submit_transcript_validation(client):
    """Test transcript submission with invalid input."""
    # Too short transcript
    response = client.post(
        "/api/v1/transcripts",
        json={"transcript": "Hi"},
    )
    assert response.status_code == 422  # Validation error


def test_submit_transcript_success():
    """Test successful transcript submission."""
    app = create_app()

    mock_session = AsyncMock()

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session

    with (
        patch("src.api.v1.routes.transcripts.TranscriptRepository") as mock_repo_class,
        patch("src.api.v1.routes.transcripts.process_transcript_task") as mock_task,
    ):
        mock_repo = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.id = "test-uuid-123"
        mock_repo.create = AsyncMock(return_value=mock_transcript)
        mock_repo_class.return_value = mock_repo

        test_client = TestClient(app)
        response = test_client.post(
            "/api/v1/transcripts",
            json={
                "transcript": "Alice and Bob discussed the Q1 roadmap in detail. "
                "Bob will create the design doc by next week.",
                "meeting_id": "mtg_001",
                "participants": ["alice@company.com", "bob@company.com"],
                "metadata": {"meeting_title": "Q1 Planning"},
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["transcript_id"] == "test-uuid-123"
        assert data["status"] == "processing"


def test_get_transcript_invalid_id(client):
    """Test getting transcript with invalid ID format."""
    response = client.get("/api/v1/transcripts/not-a-uuid")
    assert response.status_code == 400


def test_get_actions_invalid_id(client):
    """Test getting actions with invalid transcript ID."""
    response = client.get("/api/v1/actions/not-a-uuid")
    assert response.status_code == 400
