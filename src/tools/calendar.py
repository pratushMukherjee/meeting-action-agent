"""Google Calendar API tool wrapper for creating events."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import TOOL_CALLS_TOTAL, TOOL_ERRORS_TOTAL

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


class CalendarAPIError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        self.retryable = retryable
        super().__init__(f"Calendar API error: {message}")


class CalendarClient:
    """Client for Google Calendar API to create events."""

    def __init__(
        self,
        credentials_file: str | None = None,
        token_file: str | None = None,
    ):
        self.credentials_file = credentials_file or settings.google_credentials_file
        self.token_file = token_file or settings.google_token_file
        self._service = None

    def _authenticate(self):
        """Authenticate with Google OAuth2."""
        creds = None
        token_path = Path(self.token_file)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

        return creds

    def _get_service(self):
        if self._service is None:
            creds = self._authenticate()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def check_conflicts(
        self,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
    ) -> list[dict]:
        """Check for conflicting events in the given time range."""
        service = self._get_service()
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return events_result.get("items", [])

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str | None = None,
        attendees: list[str] | None = None,
        description: str = "",
        location: str = "",
        calendar_id: str = "primary",
        timezone: str = "UTC",
    ) -> dict:
        """Create a Google Calendar event.

        Args:
            start_time: ISO 8601 datetime string
            end_time: ISO 8601 datetime string (defaults to 1 hour after start)

        Returns:
            dict with keys: id, htmlLink, status
        """
        TOOL_CALLS_TOTAL.labels(tool="calendar").inc()

        try:
            if not end_time:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = start_dt + timedelta(hours=1)
                end_time = end_dt.isoformat()

            event_body: dict = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start_time, "timeZone": timezone},
                "end": {"dateTime": end_time, "timeZone": timezone},
            }

            if location:
                event_body["location"] = location

            if attendees:
                event_body["attendees"] = [{"email": email} for email in attendees]

            service = self._get_service()
            event = (
                service.events()
                .insert(calendarId=calendar_id, body=event_body, sendUpdates="all")
                .execute()
            )

            logger.info(
                "calendar_event_created",
                event_id=event.get("id"),
                summary=summary,
                start=start_time,
            )

            return {
                "id": event.get("id", ""),
                "htmlLink": event.get("htmlLink", ""),
                "status": event.get("status", "confirmed"),
            }

        except Exception as e:
            TOOL_ERRORS_TOTAL.labels(
                tool="calendar", error_type=type(e).__name__
            ).inc()
            logger.error("calendar_create_failed", error=str(e), summary=summary)
            raise CalendarAPIError(
                str(e), retryable="timeout" in str(e).lower()
            ) from e
