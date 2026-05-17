from fastapi import APIRouter, HTTPException
from loguru import logger

from src.clients.model_serving import invoke_agent
from src.models.ask import AskRequest, AskResponse

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    logger.info("ask question={!r}", request.question)
    try:
        answer = await invoke_agent(request.question)
    except Exception as exc:
        logger.exception("agent call failed for /ask")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AskResponse(question=request.question, answer=answer)
