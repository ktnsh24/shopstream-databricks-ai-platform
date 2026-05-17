from loguru import logger

from src.clients.databricks import make_client
from src.config import settings


async def invoke_agent(question: str) -> str:
    """POST a question to the Databricks Model Serving agent endpoint."""
    payload = {"messages": [{"role": "user", "content": question}]}
    logger.debug("invoke_agent endpoint={} question={!r}", settings.agent_endpoint_name, question)

    async with make_client() as client:
        response = await client.post(
            f"/serving-endpoints/{settings.agent_endpoint_name}/invocations",
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]
