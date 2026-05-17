from fastapi import APIRouter, HTTPException
from loguru import logger

from src.clients.model_serving import invoke_agent
from src.models.visualize import VisualizeRequest, VisualizeResponse

router = APIRouter()


@router.post("/visualize", response_model=VisualizeResponse)
async def visualize(request: VisualizeRequest) -> VisualizeResponse:
    logger.info("visualize question={!r}", request.question)
    try:
        answer = await invoke_agent(request.question)
    except Exception as exc:
        logger.exception("agent call failed for /visualize")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return VisualizeResponse(answer=answer)
