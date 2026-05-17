import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_agent():
    with patch("src.clients.model_serving.invoke_agent", new_callable=AsyncMock) as mock:
        yield mock
