"""Input and output safety guardrails for the ShopStream AI platform.

Two layers:
  Input guardrail  — Llama Guard classifies the user question before it reaches the LLM.
                     Questions classified UNSAFE are blocked; the LLM is never called.
  Output guardrail — regex patterns redact PII from the LLM answer before it is returned.
                     Output is never blocked, only redacted.

DE parallel:
  Input guardrail  = schema enforcement at ingestion — bad records are rejected before
                     they reach the Gold layer (the LLM).
  Output guardrail = data masking in a SQL view — sensitive columns replaced with ****
                     before non-privileged consumers see them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mlflow.deployments import get_deploy_client

# ---------------------------------------------------------------------------
# Llama Guard endpoint name
# ---------------------------------------------------------------------------
# Databricks serves Llama Guard as a foundation model endpoint.
# Enable this endpoint in the Databricks workspace:
#   Serving → Foundation Models → databricks-llama-guard-3-8b → Enable
LLAMA_GUARD_ENDPOINT = "databricks-llama-guard-3-8b"

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class GuardrailResult:
    """Result of a guardrail check.

    passed: True = the check passed (safe input, or output redacted and ready to send).
    reason: Empty string when passed=True for input checks.
            Block reason when passed=False.
            For output checks: always passed=True; reason holds the (possibly redacted) text.
    """

    passed: bool
    reason: str = field(default="")


# ---------------------------------------------------------------------------
# Input guardrail — Llama Guard
# ---------------------------------------------------------------------------


def check_input(user_question: str) -> GuardrailResult:
    """Classify user input with Llama Guard.

    Returns GuardrailResult(passed=True) if the question is safe.
    Returns GuardrailResult(passed=False, reason=...) if Llama Guard returns UNSAFE.

    Falls back to passed=True if the Llama Guard endpoint is unavailable — the
    gatekeeper in shopstream_agent_model.py is always the first line of defence.
    """
    try:
        client = get_deploy_client("databricks")
        response = client.predict(
            endpoint=LLAMA_GUARD_ENDPOINT,
            inputs={
                "messages": [{"role": "user", "content": user_question}],
                "task": "classify",
            },
        )
        classification = response.get("output") or response.get("choices", [{}])[0].get(
            "message", {}
        ).get("content", "SAFE")
        if "UNSAFE" in str(classification).upper():
            # Llama Guard returns "UNSAFE S1" etc. where S1 is the violation category.
            category = str(classification).replace("UNSAFE", "").strip()
            return GuardrailResult(passed=False, reason=f"Input blocked: {category}")
        return GuardrailResult(passed=True, reason="")
    except Exception:
        # Graceful degradation — if Llama Guard is unavailable, allow through.
        # The gatekeeper already filtered topic-irrelevant questions.
        return GuardrailResult(passed=True, reason="")


# ---------------------------------------------------------------------------
# Output guardrail — regex PII redaction
# ---------------------------------------------------------------------------

# Each tuple: (compiled regex pattern, replacement text)
# Order matters — more specific patterns should come before general ones.
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL REDACTED]"),
    # Credit/debit card numbers — 16 digits with optional spaces or dashes
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "[CARD REDACTED]"),
    # Phone numbers — 10-15 digits with optional separators and leading +
    (re.compile(r"\b\+?[\d\s\-().]{10,15}\b"), "[PHONE REDACTED]"),
]


def check_output(llm_response: str) -> GuardrailResult:
    """Redact PII patterns from the LLM response.

    Always returns passed=True — output is redacted, never blocked.
    The (possibly redacted) text is in result.reason.

    Negative assertion test: assert original_pii not in result.reason
    """
    redacted = llm_response
    for pattern, replacement in _PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return GuardrailResult(passed=True, reason=redacted)
