from fastapi import APIRouter, HTTPException
from loguru import logger

from src.clients.model_serving import invoke_agent

router = APIRouter()

_REPORT_QUESTION = (
    "Generate a full business summary report covering: "
    "current revenue metrics, top-performing products, "
    "revenue forecast for the next 7 days, and any active KPI alerts."
)


@router.post("/report")
async def report() -> dict:
    logger.info("report requested")
    try:
        answer = await invoke_agent(_REPORT_QUESTION)
    except Exception as exc:
        logger.exception("agent call failed for /report")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"answer": answer}
