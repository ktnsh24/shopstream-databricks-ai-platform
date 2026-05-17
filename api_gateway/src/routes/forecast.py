from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.clients.model_serving import invoke_agent
from src.models.forecast import ForecastResponse

router = APIRouter()


@router.get("/forecast", response_model=ForecastResponse)
async def forecast(horizon_days: int = Query(default=7, ge=1, le=90)) -> ForecastResponse:
    question = f"Forecast revenue for the next {horizon_days} days."
    logger.info("forecast horizon_days={}", horizon_days)
    try:
        answer = await invoke_agent(question)
    except Exception as exc:
        logger.exception("agent call failed for /forecast")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ForecastResponse(horizon_days=horizon_days, answer=answer)
