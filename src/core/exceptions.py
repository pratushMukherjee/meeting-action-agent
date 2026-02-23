class MeetingAgentError(Exception):
    """Base exception for the meeting action agent."""


class TranscriptParsingError(MeetingAgentError):
    """Raised when transcript parsing fails."""


class ToolExecutionError(MeetingAgentError):
    """Raised when a tool call fails."""

    def __init__(self, tool_name: str, message: str, retryable: bool = False):
        self.tool_name = tool_name
        self.retryable = retryable
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class GuardrailViolation(MeetingAgentError):
    """Raised when a guardrail check fails."""

    def __init__(self, guardrail: str, message: str):
        self.guardrail = guardrail
        super().__init__(f"Guardrail '{guardrail}' violated: {message}")


class RateLimitExceeded(MeetingAgentError):
    """Raised when rate limit is exceeded."""


class BudgetExceeded(MeetingAgentError):
    """Raised when token budget is exceeded."""


class HumanApprovalRequired(MeetingAgentError):
    """Raised when an action requires human approval before proceeding."""


class HumanApprovalRejected(MeetingAgentError):
    """Raised when a human rejects the proposed execution plan."""
