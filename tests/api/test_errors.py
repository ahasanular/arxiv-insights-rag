from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_validation_error_envelope() -> None:
    # Sending a missing field to a POST endpoint should trigger a 422
    response = client.post("/api/v1/ask", json={})
    assert response.status_code == 422

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in data["error"]
    assert "details" in data["error"]
    assert len(data["error"]["details"]) > 0


def test_http_exception_envelope() -> None:
    # Sending to a non-existent route should trigger a 404
    response = client.get("/api/v1/does_not_exist")
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"
    assert data["error"]["message"] == "Not Found"
