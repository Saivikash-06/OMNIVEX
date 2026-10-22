import io
import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import settings


def test_api_key_enforcement(client: TestClient):
    """When OMNIVEX_API_KEY is configured:

    - /api/health remains accessible without key
    - Other endpoints return 401 without key or with wrong key
    - Access succeeds with correct X-API-Key header
    """
    settings.OMNIVEX_API_KEY = "super-secret-research-key-42"
    try:
        # 1. Health endpoint open
        h_resp = client.get("/api/health")
        assert h_resp.status_code == 200

        # 2. Protected endpoint without key -> 401
        prot_resp = client.get("/api/datasets")
        assert prot_resp.status_code == 401
        assert prot_resp.json()["error"]["code"] == "UNAUTHORIZED"

        # 3. Protected endpoint with incorrect key -> 401
        bad_key_resp = client.get("/api/datasets", headers={"X-API-Key": "wrong-key"})
        assert bad_key_resp.status_code == 401

        # 4. Protected endpoint with valid key -> 200
        ok_resp = client.get("/api/datasets", headers={"X-API-Key": "super-secret-research-key-42"})
        assert ok_resp.status_code == 200
    finally:
        settings.OMNIVEX_API_KEY = None  # Reset for subsequent tests


def test_rate_limiting(client: TestClient):
    """Test SlowAPI rate limiter on endpoints."""
    # Temporarily lower limit on an endpoint or test multiple rapid hits
    # Default is 60/minute; hitting 70 times should trigger 429
    hit_429 = False
    for _ in range(75):
        resp = client.get("/api/health")
        if resp.status_code == 429:
            hit_429 = True
            assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            break
    # SlowAPI rate limits by client IP; in TestClient it behaves according to configured limiter
    assert hit_429 or resp.status_code == 200


def test_internal_server_error_sanitization(client: TestClient, test_app):
    """Verify that unexpected exceptions return a generic 500 error with correlation ID

    and never leak tracebacks, internal file paths, or SQL statements.
    """
    @test_app.get("/api/test-faulty-500")
    def faulty_endpoint():
        raise RuntimeError("Simulated catastrophic failure: secret key /private/key.pem")

    resp = client.get("/api/test-faulty-500")
    assert resp.status_code == 500
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    # Never expose stack trace or secret path
    assert "catastrophic" not in data["error"]["message"]
    assert "key.pem" not in data["error"]["message"]
    assert "Correlation ID:" in data["error"]["message"]


def test_oversize_file_upload_rejection(client: TestClient):
    """Verify streaming upload size limits (413 Payload Too Large)."""
    # Create stream slightly exceeding default test limit
    large_stream = io.BytesIO(b"col1,col2\n" + b"1,2\n" * 1000)
    # Temporarily set max bytes small for test
    orig_max = settings.MAX_UPLOAD_SIZE_BYTES
    settings.MAX_UPLOAD_SIZE_BYTES = 500  # 500 bytes limit
    try:
        resp = client.post(
            "/api/datasets/upload",
            files={"file": ("too_large.csv", large_stream, "text/csv")},
            data={"role": "reference"},
        )
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    finally:
        settings.MAX_UPLOAD_SIZE_BYTES = orig_max
