"""Supervisor agent — routes incoming questions to the right specialist.

The supervisor does NOT call an LLM itself.  It reads the question, matches
keywords against routing rules, and delegates to the correct specialist agent.
If no rule matches, the customer agent acts as the default fallback.

Courier analogy: the supervisor is the scanner at the depot entrance. Every
incoming parcel (question) gets a label read. Fraud parcels go to the
security bay. Pricing parcels go to the billing desk. Everything else goes
to the VIP customer desk. The scanner never opens a parcel — it only decides
which bay handles it.

Routing rules are checked in order — FRAUD first, PRICING second, CUSTOMER
third.  This ordering matters: a question like "why was this customer's order
blocked for fraud?" mentions both customer and fraud keywords. Checking fraud
first ensures it is never misrouted to the customer agent.
"""

from __future__ import annotations

import logging

from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing table
# Order matters — the first matching rule wins.
# ---------------------------------------------------------------------------

ROUTING_RULES: list[tuple[list[str], str]] = [
    (
        ["fraud", "blocked", "chargeback", "suspicious", "decline", "flagged", "anomaly"],
        "fraud",
    ),
    (
        ["price", "margin", "revenue", "pricing", "profit", "discount", "product", "billing"],
        "pricing",
    ),
    (
        ["customer", "profile", "lifetime", "ltv", "churn", "loyalty", "segment", "retention"],
        "customer",
    ),
]

_DEFAULT_AGENT = "customer"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route(question: str) -> str:
    """Return the agent name that should handle this question.

    Args:
        question: the user's question (any case)

    Returns:
        one of: 'fraud', 'pricing', 'customer'
    """
    lower = question.lower()
    for keywords, agent_name in ROUTING_RULES:
        if any(kw in lower for kw in keywords):
            return agent_name
    return _DEFAULT_AGENT


def run(question: str, client: OpenAI | None = None) -> dict[str, str]:
    """Route the question to the right specialist and return the answer.

    The client is passed through to the specialist so only one OpenAI
    connection is opened per request.

    Args:
        question: the user's question
        client:   optional pre-built OpenAI client; each sub-agent creates
                  its own if not provided

    Returns:
        dict with keys:
            'agent'  — which specialist handled it ('fraud', 'pricing', 'customer')
            'answer' — the plain-text answer from the specialist
    """
    agent_name = route(question)
    logger.debug("supervisor routing to agent=%s", agent_name)

    if agent_name == "fraud":
        # Dual import: package path for local dev, bare module name in MLflow serving
        try:
            from ai_platform.agents.fraud_agent import run as _run
        except ImportError:
            from fraud_agent import run as _run  # type: ignore[no-redef]

    elif agent_name == "pricing":
        try:
            from ai_platform.agents.pricing_agent import run as _run
        except ImportError:
            from pricing_agent import run as _run  # type: ignore[no-redef]

    else:
        try:
            from ai_platform.agents.customer_agent import run as _run
        except ImportError:
            from customer_agent import run as _run  # type: ignore[no-redef]

    answer = _run(question, client)  # type: ignore[possibly-undefined]
    return {"agent": agent_name, "answer": answer}
