"""Jira REST API tool wrapper for creating and managing issues."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_base, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logging import get_logger
from src.core.metrics import TOOL_CALLS_TOTAL, TOOL_ERRORS_TOTAL

logger = get_logger(__name__)


class JiraAPIError(Exception):
    def __init__(self, status_code: int, message: str, retryable: bool = False):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(f"Jira API error ({status_code}): {message}")


class _retry_if_retryable_jira_error(retry_base):
    """Only retry JiraAPIError when retryable=True."""

    def __call__(self, retry_state):
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        return isinstance(exc, JiraAPIError) and exc.retryable


class JiraClient:
    """Async client for Jira REST API v3."""

    def __init__(
        self,
        server_url: str | None = None,
        user_email: str | None = None,
        api_token: str | None = None,
    ):
        self.server_url = (server_url or settings.jira_server_url).rstrip("/")
        self.user_email = user_email or settings.jira_user_email
        self.api_token = api_token or settings.jira_api_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.server_url}/rest/api/3",
                auth=(self.user_email, self.api_token),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=_retry_if_retryable_jira_error(),
        before_sleep=lambda retry_state: logger.warning(
            "jira_retry",
            attempt=retry_state.attempt_number,
        ),
        reraise=True,
    )
    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        assignee: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Create a Jira issue.

        Returns:
            dict with keys: key, id, self (URL)
        """
        TOOL_CALLS_TOTAL.labels(tool="jira").inc()

        # Build ADF description
        description_content = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}],
                }
            ],
        }

        fields: dict = {
            "project": {"key": project_key},
            "summary": summary,
            "description": description_content,
            "issuetype": {"name": issue_type},
        }

        if assignee:
            fields["assignee"] = {"displayName": assignee}
        if priority:
            priority_map = {"high": "High", "medium": "Medium", "low": "Low"}
            fields["priority"] = {"name": priority_map.get(priority.lower(), "Medium")}
        if labels:
            fields["labels"] = labels

        payload = {"fields": fields}

        client = await self._get_client()
        response = await client.post("/issue", json=payload)

        if response.status_code == 201:
            data = response.json()
            issue_key = data["key"]
            logger.info("jira_issue_created", key=issue_key)
            return {
                "key": issue_key,
                "id": data["id"],
                "url": f"{self.server_url}/browse/{issue_key}",
            }

        # Handle errors
        error_msg = response.text
        retryable = response.status_code in (429, 500, 502, 503)
        TOOL_ERRORS_TOTAL.labels(
            tool="jira", error_type=str(response.status_code)
        ).inc()

        if not retryable:
            logger.error(
                "jira_create_failed_permanent",
                status_code=response.status_code,
                error=error_msg,
            )

        raise JiraAPIError(response.status_code, error_msg, retryable=retryable)
