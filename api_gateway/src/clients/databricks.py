import httpx

from src.config import settings


def _make_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.databricks_token}",
        "Content-Type": "application/json",
    }


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.databricks_host,
        headers=_make_headers(),
        timeout=settings.request_timeout_seconds,
    )
