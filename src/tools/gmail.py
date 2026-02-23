"""Gmail API tool wrapper for sending emails."""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import TOOL_CALLS_TOTAL, TOOL_ERRORS_TOTAL

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailAPIError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        self.retryable = retryable
        super().__init__(f"Gmail API error: {message}")


class GmailClient:
    """Client for Gmail API to send emails."""

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
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def send_email(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        sender: str = "me",
    ) -> dict:
        """Send an email via Gmail API.

        Returns:
            dict with keys: id, threadId
        """
        TOOL_CALLS_TOTAL.labels(tool="email").inc()

        try:
            message = MIMEText(body, "html")
            message["to"] = ", ".join(to)
            message["subject"] = subject
            if cc:
                message["cc"] = ", ".join(cc)

            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode("utf-8")

            service = self._get_service()
            result = (
                service.users()
                .messages()
                .send(userId=sender, body={"raw": raw_message})
                .execute()
            )

            logger.info(
                "email_sent",
                message_id=result.get("id"),
                recipients=to,
                subject=subject,
            )
            return {
                "id": result.get("id", ""),
                "threadId": result.get("threadId", ""),
                "recipients": to,
                "subject": subject,
            }

        except Exception as e:
            TOOL_ERRORS_TOTAL.labels(tool="email", error_type=type(e).__name__).inc()
            logger.error("email_send_failed", error=str(e), recipients=to)
            raise GmailAPIError(str(e), retryable="timeout" in str(e).lower()) from e
