from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.limiter import limiter
from app.db.session import get_db_session
from app.main import app


async def mock_db_session() -> AsyncGenerator[AsyncMock, None]:
    # Return a dummy mock that doesn't actually hit postgres
    mock_session = AsyncMock()
    # Mock the return values for the stats endpoint
    mock_session.scalar = AsyncMock(return_value=1)

    # Mock execute for dates
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_result.one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=mock_result)

    yield mock_session


@pytest.fixture
def override_db()->Any:
    app.dependency_overrides[get_db_session] = mock_db_session
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_rate_limit_envelope(override_db: Any)->None:
    # Reset limiter memory for this IP
    limiter.reset()

    success_count = 0
    rate_limited = False

    for _ in range(65):
        response = client.get("/api/v1/stats/summary")
        if response.status_code == 200:
            success_count += 1
        elif response.status_code == 429:
            rate_limited = True
            data = response.json()
            assert "error" in data
            assert data["error"]["code"] == "TOO_MANY_REQUESTS"
            break

    assert rate_limited is True
    assert success_count == 60
