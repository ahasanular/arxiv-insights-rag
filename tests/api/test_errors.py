import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_validation_error_envelope():
    # Sending a string to 'limit' which expects an integer should trigger a 422
    response = client.get("/api/v1/stats/top-authors?limit=not_an_int")
    assert response.status_code == 422
    
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in data["error"]
    assert "details" in data["error"]
    assert len(data["error"]["details"]) > 0

def test_http_exception_envelope():
    # Sending to a non-existent route should trigger a 404
    response = client.get("/api/v1/does_not_exist")
    assert response.status_code == 404
    
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"
    assert data["error"]["message"] == "Not Found"
