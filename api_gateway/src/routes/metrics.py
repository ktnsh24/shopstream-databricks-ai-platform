from fastapi import APIRouter, HTTPException
from loguru import logger

from src.clients.model_serving import invoke_agent
from src.models.metrics import MetricsResponse

router = APIRouter()

_METRICS_QUESTION = (
    "What are the current revenue metrics? "
    "Include total revenue, order count, and average order value."
)


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    logger.info("metrics requested")
    try:
        answer = await invoke_agent(_METRICS_QUESTION)
    except Exception as exc:
        logger.exception("agent call failed for /metrics")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MetricsResponse(answer=answer)
