"""Tests for supervisor routing and delegation.

These tests cover the pure keyword-routing logic — no LLM calls, no Databricks
connection required.  They run locally with 'pytest tests/agents/'.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from ai_platform.agents.supervisor import _DEFAULT_AGENT, ROUTING_RULES, route, run

# ---------------------------------------------------------------------------
# route() — keyword routing, no external dependencies
# ---------------------------------------------------------------------------

class TestRoute:
    def test_fraud_keyword_blocked(self):
        assert route("Why was order 999 blocked?") == "fraud"

    def test_fraud_keyword_chargeback(self):
        assert route("How many chargebacks last month?") == "fraud"

    def test_fraud_keyword_suspicious(self):
        assert route("This transaction looks suspicious") == "fraud"

    def test_fraud_keyword_flagged(self):
        assert route("Order 1234 was flagged — why?") == "fraud"

    def test_pricing_keyword_revenue(self):
        assert route("What was total revenue last 7 days?") == "pricing"

    def test_pricing_keyword_margin(self):
        assert route("Why is margin low in Electronics?") == "pricing"

    def test_pricing_keyword_discount(self):
        assert route("How much discount did we give out this month?") == "pricing"

    def test_pricing_keyword_product(self):
        assert route("Which product is selling best?") == "pricing"

    def test_customer_keyword_ltv(self):
        assert route("What is the average LTV of high-risk customers?") == "customer"

    def test_customer_keyword_churn(self):
        assert route("How many customers are in the high churn segment?") == "customer"

    def test_customer_keyword_profile(self):
        assert route("Show me the customer segment breakdown") == "customer"

    def test_unknown_question_defaults_to_customer(self):
        assert route("Hello, how are you?") == _DEFAULT_AGENT

    def test_empty_question_defaults_to_customer(self):
        assert route("") == _DEFAULT_AGENT

    def test_case_insensitive_routing(self):
        assert route("FRAUD DETECTED on order 42") == "fraud"
        assert route("REVENUE this week") == "pricing"

    def test_fraud_takes_priority_over_customer(self):
        """A question mentioning both fraud and customer keywords — fraud wins.

        The ROUTING_RULES list checks fraud first, so 'blocked' + 'customer' hits
        the fraud rule before the customer rule.
        """
        assert route("Why was this customer's order blocked for fraud?") == "fraud"

    def test_fraud_takes_priority_over_pricing(self):
        """'revenue' + 'chargeback' — fraud rule is checked first."""
        assert route("Did the chargeback affect our revenue figures?") == "fraud"

    def test_routing_rules_ordering(self):
        """The first rule in ROUTING_RULES must be fraud (highest priority)."""
        assert ROUTING_RULES[0][1] == "fraud"
        assert ROUTING_RULES[1][1] == "pricing"


# ---------------------------------------------------------------------------
# run() — delegation to specialist, no real LLM
# ---------------------------------------------------------------------------

class TestRun:
    @patch("ai_platform.agents.fraud_agent.OpenAI")
    def test_routes_fraud_and_returns_agent_name(self, mock_openai_cls):
        """Supervisor returns dict with 'agent' and 'answer' keys for fraud questions."""
        # Build a fake OpenAI client that returns a direct (no-tool-call) response
        fake_msg = MagicMock()
        fake_msg.tool_calls = None
        fake_msg.content = "Order 999 has a high fraud score."
        fake_msg.model_dump.return_value = {"role": "assistant", "content": fake_msg.content}

        fake_choice = MagicMock()
        fake_choice.message = fake_msg

        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = run("Why was order 999 blocked?", client=mock_client)

        assert result["agent"] == "fraud"
        assert "fraud score" in result["answer"]

    @patch("ai_platform.agents.pricing_agent.OpenAI")
    def test_routes_pricing_and_returns_agent_name(self, mock_openai_cls):
        fake_msg = MagicMock()
        fake_msg.tool_calls = None
        fake_msg.content = "Revenue last 7 days: EUR 109,428."
        fake_msg.model_dump.return_value = {"role": "assistant", "content": fake_msg.content}

        fake_choice = MagicMock()
        fake_choice.message = fake_msg

        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = run("What was revenue this week?", client=mock_client)

        assert result["agent"] == "pricing"
        assert "109,428" in result["answer"]

    @patch("ai_platform.agents.customer_agent.OpenAI")
    def test_routes_unknown_to_customer_default(self, mock_openai_cls):
        fake_msg = MagicMock()
        fake_msg.tool_calls = None
        fake_msg.content = "I can help with customer data."
        fake_msg.model_dump.return_value = {"role": "assistant", "content": fake_msg.content}

        fake_choice = MagicMock()
        fake_choice.message = fake_msg

        fake_response = MagicMock()
        fake_response.choices = [fake_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = run("Hello, what can you tell me?", client=mock_client)

        assert result["agent"] == "customer"

    def test_run_returns_dict_with_required_keys(self):
        """run() must always return a dict with 'agent' and 'answer'."""
        mock_client = MagicMock()
        fake_msg = MagicMock()
        fake_msg.tool_calls = None
        fake_msg.content = "Test answer."
        fake_msg.model_dump.return_value = {"role": "assistant", "content": "Test answer."}

        fake_choice = MagicMock()
        fake_choice.message = fake_msg

        fake_response = MagicMock()
        fake_response.choices = [fake_choice]
        mock_client.chat.completions.create.return_value = fake_response

        result = run("How are we doing?", client=mock_client)

        assert "agent" in result
        assert "answer" in result
        assert isinstance(result["agent"], str)
        assert isinstance(result["answer"], str)


# ---------------------------------------------------------------------------
# Tool-call loop — verify supervisor passes through multi-turn correctly
# ---------------------------------------------------------------------------

class TestFraudToolCallLoop:
    """Verify that sub-agents handle the two-call LLM pattern correctly."""

    @patch("ai_platform.agents.fraud_agent._run_sql")
    def test_fraud_agent_calls_tool_and_returns_final_answer(self, mock_run_sql):
        """When the LLM asks for a tool, the agent runs it and calls the LLM again."""
        mock_run_sql.return_value = (
            "day  revenue_eur  rolling_avg_14d_eur  pct_below_avg\n"
            "2026-05-10  50.00  200.00  75.0"
        )

        # First LLM call: LLM asks for the tool
        tool_call_msg = MagicMock()
        tool_call_msg.content = None
        tool_call_msg.model_dump.return_value = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "tc1",
                "function": {
                    "name": "check_revenue_anomalies",
                    "arguments": json.dumps({"period": "last 7 days"}),
                },
            }],
        }
        tc = MagicMock()
        tc.id = "tc1"
        tc.function.name = "check_revenue_anomalies"
        tc.function.arguments = json.dumps({"period": "last 7 days"})
        tool_call_msg.tool_calls = [tc]

        tool_call_response = MagicMock()
        tool_call_response.choices = [MagicMock(message=tool_call_msg)]

        # Second LLM call: LLM writes final answer
        final_msg = MagicMock()
        final_msg.tool_calls = None
        final_msg.content = "On 2026-05-10 revenue was 75% below average — possible fraud event."
        final_response = MagicMock()
        final_response.choices = [MagicMock(message=final_msg)]

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            tool_call_response,
            final_response,
        ]

        from ai_platform.agents.fraud_agent import run as fraud_run
        answer = fraud_run("Are there any anomalies last 7 days?", client=mock_client)

        assert mock_run_sql.called, "SQL tool should have been called"
        assert "75%" in answer or "75" in answer
        assert mock_client.chat.completions.create.call_count == 2
