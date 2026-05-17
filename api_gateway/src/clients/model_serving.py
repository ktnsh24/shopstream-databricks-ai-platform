from loguru import logger

from src.clients.databricks import make_client
from src.config import settings


async def invoke_agent(question: str) -> str:
    """POST a question to the Databricks Model Serving agent endpoint."""
    # PyFunc models expect dataframe_records format
    payload = {"dataframe_records": [{"question": question}]}
    logger.debug("invoke_agent endpoint={} question={!r}", settings.agent_endpoint_name, question)

    try:
        async with make_client() as client:
            response = await client.post(
                f"/serving-endpoints/{settings.agent_endpoint_name}/invocations",
                json=payload,
            )
        response.raise_for_status()
    except Exception as exc:
        raise Exception(f"{exc} — body: {response.text[:500]}") from exc

    data = response.json()
    # PyFunc model serving returns {"predictions": [{"answer": "..."}]}
    predictions = data.get("predictions", [])
    if predictions and isinstance(predictions[0], dict):
        return predictions[0].get("answer", str(predictions[0]))
    return str(predictions[0]) if predictions else ""
