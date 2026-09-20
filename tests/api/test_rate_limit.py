import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db_session
from app.api.limiter import limiter
from slowapi.util import get_remote_address


async def mock_db_session():
    # Return a dummy mock that doesn't actually hit postgres
    from unittest.mock import AsyncMock, MagicMock
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
def override_db():
    app.dependency_overrides[get_db_session] = mock_db_session
    yield
    app.dependency_overrides.clear()


client = TestClient(app)

def test_rate_limit_envelope(override_db):
    # Hit the stats summary endpoint, which has a 60/minute limit
    # We will hit it 61 times to trigger the 429
    
    # We should override the limit for this specific test so we don't have to hit it 60 times.
    # But since it's hardcoded to 60/minute in the decorator, we'll just hit it 65 times.
    # It's an in-memory limit, so it's very fast.
    
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
