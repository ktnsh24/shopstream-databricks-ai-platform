"""
Minimal ShopStream agent example — one tool, full loop.

This file is a learning exercise. It has NO real database.
All "data" is a Python list at the top of this file.
Replace that list with a real SQL query later — nothing else changes.

Run with:
    export OPENAI_API_KEY=sk-...
    python minimal_agent_example.py

Or swap OPENAI_API_KEY + base_url to use Databricks:
    export DATABRICKS_TOKEN=dapi...
    export DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
    # then change the client setup below (see comment inside build_client())
"""

import json
import os

from openai import OpenAI


# =============================================================================
# FAKE DATA — replace this with a real SQL query later
#
# Imagine this is the result of:
#   SELECT product_name, return_rate_pct, units_sold
#   FROM helix_gold.products.fct_product_performance
#   ORDER BY return_rate_pct DESC
# =============================================================================

FAKE_PRODUCT_DATA = [
    {"product_name": "Alpine Pro Tent",     "return_rate_pct": 23.4, "units_sold": 412},
    {"product_name": "TrailBlazer Boots",   "return_rate_pct": 18.1, "units_sold": 890},
    {"product_name": "Summit Sleeping Bag", "return_rate_pct": 9.2,  "units_sold": 634},
    {"product_name": "MeshRun T-Shirt",     "return_rate_pct": 4.7,  "units_sold": 2103},
    {"product_name": "HydroFlask 32oz",     "return_rate_pct": 2.1,  "units_sold": 3421},
]

FAKE_REVENUE_DATA = [
    {"date": "2026-05-12", "revenue_eur": 42310},
    {"date": "2026-05-11", "revenue_eur": 38920},
    {"date": "2026-05-10", "revenue_eur": 51440},
    {"date": "2026-05-09", "revenue_eur": 47800},
    {"date": "2026-05-08", "revenue_eur": 39100},
]


# =============================================================================
# STEP 1 — THE TOOL FUNCTION
#
# This is the Python function YOU write. The LLM cannot run code —
# it tells you which function to call and with what arguments.
# Your Python code runs the function and returns the result as a string.
# =============================================================================

def query_shopstream_data(table: str, limit: int = 5) -> str:
    """
    Query ShopStream data.

    In this example we return fake in-memory data.
    In production, replace with:
        df = spark.read.table(f"helix_gold.{table}")
        return df.limit(limit).toPandas().to_json(orient="records")

    Returns a JSON string — always a string, because the LLM reads it like text.
    """
    if table == "product_performance":
        rows = FAKE_PRODUCT_DATA[:limit]
    elif table == "revenue_daily":
        rows = FAKE_REVENUE_DATA[:limit]
    else:
        # Always validate the input — the LLM might ask for a table that doesn't exist
        return json.dumps({"error": f"Unknown table '{table}'. Choose: product_performance, revenue_daily"})

    return json.dumps(rows)


# =============================================================================
# STEP 2 — THE TOOL DESCRIPTION
#
# This is the JSON schema you write ONCE per tool.
# The LLM reads this and decides:
#   - WHEN to call this function (from the description)
#   - WHAT arguments to pass (from the parameters section)
# =============================================================================

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_shopstream_data",
        "description": (
            "Query ShopStream e-commerce data. "
            "Use 'product_performance' for product return rates, units sold, or product rankings. "
            "Use 'revenue_daily' for daily revenue figures. "
            "Always use this tool when the user asks about ShopStream metrics."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "enum": ["product_performance", "revenue_daily"],
                    "description": "Which table to query",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many rows to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["table"],
        },
    },
}


# =============================================================================
# STEP 3 — THE CLIENT
# =============================================================================

def build_client() -> OpenAI:
    """
    Build the OpenAI client.

    To use Databricks instead:
        return OpenAI(
            api_key=os.environ["DATABRICKS_TOKEN"],
            base_url=os.environ["DATABRICKS_HOST"].rstrip("/") + "/serving-endpoints",
        )
        # Then change model= below to "databricks-meta-llama-3-3-70b-instruct"
    """
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


# =============================================================================
# STEP 4 — THE LOOP
#
# This is the full agent loop. Read it line by line.
#
# Round 1: LLM reads the question + tool description → decides to call the tool
# Round 2: You run the tool → feed result back → LLM writes the final answer
# =============================================================================

def run_agent(question: str) -> str:
    client = build_client()

    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}")

    # Start the conversation with just the user's question
    messages = [
        {
            "role": "system",
            "content": (
                "You are a data assistant for ShopStream, a Dutch e-commerce company. "
                "Always use the query_shopstream_data tool to get real data before answering. "
                "Never make up numbers."
            ),
        },
        {"role": "user", "content": question},
    ]

    # -------------------------------------------------------------------------
    # Round 1 — LLM decides what tool to call
    # -------------------------------------------------------------------------
    print("\n[Round 1] Asking LLM which tool to call...")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=[TOOL_SCHEMA],
        tool_choice="auto",   # LLM decides: call a tool OR answer directly
    )

    assistant_message = response.choices[0].message

    if not assistant_message.tool_calls:
        # LLM decided it doesn't need a tool — answer directly
        print("[Round 1] LLM answered directly (no tool needed)")
        return assistant_message.content

    # LLM wants to call a tool — print what it decided
    tool_call = assistant_message.tool_calls[0]
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)

    print(f"[Round 1] LLM chose tool: {tool_name!r}")
    print(f"[Round 1] LLM chose args: {tool_args}")

    # -------------------------------------------------------------------------
    # Run YOUR function
    # This is the step that replaces you manually running a SQL query
    # -------------------------------------------------------------------------
    print(f"\n[Tool] Running {tool_name}({tool_args})...")
    tool_result = query_shopstream_data(**tool_args)
    print(f"[Tool] Result: {tool_result[:120]}...")   # truncate for display

    # -------------------------------------------------------------------------
    # Round 2 — Feed the result back to the LLM
    # -------------------------------------------------------------------------
    print("\n[Round 2] Feeding result back to LLM for final answer...")

    messages.append(assistant_message)           # the LLM's tool request
    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": tool_result,                  # YOUR function's output
    })

    final_response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=[TOOL_SCHEMA],
    )

    answer = final_response.choices[0].message.content
    print(f"\n[Answer] {answer}")
    return answer


# =============================================================================
# RUN IT
# =============================================================================

if __name__ == "__main__":
    questions = [
        "Which product has the highest return rate?",
        "What was our revenue on the last 3 days?",
        "Show me the top 3 products by return rate",
    ]

    for q in questions:
        run_agent(q)
        print()
