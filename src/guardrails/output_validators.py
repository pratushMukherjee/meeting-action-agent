"""Output guardrails: schema validation, content filtering, PII scrubbing."""

from __future__ import annotations

import re

from pydantic import ValidationError

from src.agent.state import ActionItem
from src.core.exceptions import GuardrailViolation
from src.core.logging import get_logger
from src.core.metrics import GUARDRAIL_VIOLATIONS
from src.guardrails.input_validators import PII_PATTERNS

logger = get_logger(__name__)


def validate_action_items(items: list[dict]) -> list[ActionItem]:
    """Validate extracted action items against the schema.

    Returns validated ActionItem objects.
    Raises GuardrailViolation for invalid items.
    """
    validated = []
    for i, item_data in enumerate(items):
        try:
            item = ActionItem.model_validate(item_data)
            validated.append(item)
        except ValidationError as e:
            logger.warning(
                "invalid_action_item",
                index=i,
                errors=e.error_count(),
            )
            GUARDRAIL_VIOLATIONS.labels(guardrail_type="invalid_action_item").inc()

    return validated


def filter_low_confidence(
    items: list[ActionItem],
    threshold: float = 0.7,
) -> tuple[list[ActionItem], list[ActionItem]]:
    """Split action items into high-confidence and low-confidence groups.

    Returns:
        Tuple of (high_confidence_items, low_confidence_items)
    """
    high = [item for item in items if item.confidence >= threshold]
    low = [item for item in items if item.confidence < threshold]

    if low:
        logger.info(
            "low_confidence_items_filtered",
            count=len(low),
            threshold=threshold,
        )
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="low_confidence").inc()

    return high, low


def scrub_pii_from_output(text: str) -> str:
    """Remove PII patterns from generated output text."""
    for pattern in PII_PATTERNS.values():
        text = pattern.sub("[REDACTED]", text)
    return text


def validate_email_content(subject: str, body: str) -> None:
    """Validate generated email content for safety."""
    # Check for PII leakage
    for field_name, text in [("subject", subject), ("body", body)]:
        for pii_type, pattern in PII_PATTERNS.items():
            if pattern.search(text):
                GUARDRAIL_VIOLATIONS.labels(guardrail_type="pii_in_email").inc()
                raise GuardrailViolation(
                    "email_content",
                    f"PII ({pii_type}) detected in email {field_name}",
                )

    # Check for excessive length
    if len(body) > 50000:
        raise GuardrailViolation("email_content", "Email body too long (max 50000 chars)")

    # Check for suspicious patterns (potential hallucination markers)
    hallucination_markers = [
        re.compile(r"as an ai", re.IGNORECASE),
        re.compile(r"i don't have access to", re.IGNORECASE),
        re.compile(r"i cannot verify", re.IGNORECASE),
    ]
    for marker in hallucination_markers:
        if marker.search(body):
            GUARDRAIL_VIOLATIONS.labels(guardrail_type="hallucination_detected").inc()
            logger.warning("potential_hallucination_in_email", pattern=marker.pattern)


def validate_jira_payload(payload: dict) -> None:
    """Validate Jira ticket payload before API submission."""
    required_fields = ["summary", "description"]
    for field in required_fields:
        if not payload.get(field):
            raise GuardrailViolation(
                "jira_payload",
                f"Missing required Jira field: {field}",
            )

    if len(payload.get("summary", "")) > 255:
        raise GuardrailViolation("jira_payload", "Jira summary too long (max 255 chars)")
