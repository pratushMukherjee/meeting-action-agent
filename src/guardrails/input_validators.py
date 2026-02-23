"""Input guardrails: transcript validation, PII detection, injection defense."""

from __future__ import annotations

import re

from src.core.exceptions import GuardrailViolation
from src.core.logging import get_logger
from src.core.metrics import GUARDRAIL_VIOLATIONS

logger = get_logger(__name__)

# PII patterns
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "email_with_password": re.compile(
        r"password\s*[:=]\s*\S+", re.IGNORECASE
    ),
    "api_key": re.compile(
        r"(?:api[_-]?key|secret|token)\s*[:=]\s*['\"]?\S{20,}['\"]?", re.IGNORECASE
    ),
}

# Prompt injection patterns
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
]

MIN_TRANSCRIPT_LENGTH = 10
MAX_TRANSCRIPT_LENGTH = 100_000


def validate_transcript(transcript: str) -> str:
    """Validate transcript content for safety and quality.

    Returns the validated transcript text.
    Raises GuardrailViolation if validation fails.
    """
    # Length check
    if len(transcript) < MIN_TRANSCRIPT_LENGTH:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="transcript_too_short").inc()
        raise GuardrailViolation(
            "transcript_validation",
            f"Transcript too short (min {MIN_TRANSCRIPT_LENGTH} chars)",
        )

    if len(transcript) > MAX_TRANSCRIPT_LENGTH:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="transcript_too_long").inc()
        raise GuardrailViolation(
            "transcript_validation",
            f"Transcript too long (max {MAX_TRANSCRIPT_LENGTH} chars)",
        )

    # Encoding validation
    try:
        transcript.encode("utf-8")
    except UnicodeEncodeError as e:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="invalid_encoding").inc()
        raise GuardrailViolation("transcript_validation", "Invalid text encoding") from e

    return transcript


def detect_pii(text: str) -> list[dict]:
    """Scan text for PII patterns.

    Returns a list of detected PII items with type and position.
    """
    detections = []
    for pii_type, pattern in PII_PATTERNS.items():
        matches = pattern.finditer(text)
        for match in matches:
            detections.append({
                "type": pii_type,
                "start": match.start(),
                "end": match.end(),
                "matched": match.group()[:10] + "...",  # Truncate for logging
            })

    if detections:
        GUARDRAIL_VIOLATIONS.labels(guardrail_type="pii_detected").inc()
        logger.warning(
            "pii_detected_in_transcript",
            pii_types=[d["type"] for d in detections],
            count=len(detections),
        )

    return detections


def redact_pii(text: str) -> str:
    """Redact detected PII from text, replacing with [REDACTED]."""
    for pattern in PII_PATTERNS.values():
        text = pattern.sub("[REDACTED]", text)
    return text


def check_prompt_injection(text: str) -> bool:
    """Check if text contains prompt injection attempts.

    Returns True if injection patterns are detected.
    """
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            GUARDRAIL_VIOLATIONS.labels(guardrail_type="prompt_injection").inc()
            logger.warning("prompt_injection_detected", pattern=pattern.pattern)
            return True
    return False


def validate_and_sanitize(transcript: str) -> str:
    """Full input validation pipeline.

    1. Validate transcript structure
    2. Check for prompt injection
    3. Detect and redact PII

    Returns sanitized transcript text.
    """
    validated = validate_transcript(transcript)

    if check_prompt_injection(validated):
        raise GuardrailViolation(
            "prompt_injection",
            "Potential prompt injection detected in transcript",
        )

    sanitized = redact_pii(validated)
    return sanitized
