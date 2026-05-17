from fastapi import APIRouter, HTTPException
from loguru import logger

from src.clients.model_serving import invoke_agent

router = APIRouter()

_ALERTS_QUESTION = (
    "Are there any active KPI alerts or anomalies in the current metrics? "
    "List each alert with its severity and recommended action."
)


@router.get("/alerts")
async def alerts() -> dict:
    logger.info("alerts requested")
    try:
        answer = await invoke_agent(_ALERTS_QUESTION)
    except Exception as exc:
        logger.exception("agent call failed for /alerts")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"answer": answer}
