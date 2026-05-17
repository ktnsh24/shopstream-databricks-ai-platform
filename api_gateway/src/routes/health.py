from fastapi import APIRouter

from src.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.environment,
        "agent_endpoint": settings.agent_endpoint_name,
    }
