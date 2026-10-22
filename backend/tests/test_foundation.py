from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"
    assert data["database"] == "connected"
    assert "timestamp" in data
    assert data["environment"] == "research"


def test_security_headers_present(client: TestClient):
    response = client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_correlation_id_header(client: TestClient):
    response = client.get("/api/health", headers={"X-Correlation-ID": "custom-trace-123"})
    assert response.headers.get("X-Correlation-ID") == "custom-trace-123"


def test_not_found_error_format(client: TestClient):
    response = client.get("/api/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    # FastAPI default 404 or our handler
    assert "detail" in data or "error" in data
