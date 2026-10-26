import logging
import json
from fastapi.testclient import TestClient
from app.main import app
from app.core.logging_config import redact_sensitive_data, StructuredJsonFormatter

client = TestClient(app)


def test_legacy_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "uptime_seconds" in data


def test_liveness_probe():
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data
    assert "uptime_seconds" in data


def test_readiness_probe():
    response = client.get("/health/ready")
    # In local test mode with SQLite and without Redis, it returns 200 (ready or degraded)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "degraded")
    assert "checks" in data
    checks = data["checks"]
    assert checks["database"]["status"] == "healthy"
    assert checks["schema"]["status"] == "healthy"
    assert "document_engines" in checks
    assert checks["document_engines"]["status"] == "healthy"


def test_sensitive_data_redaction():
    raw_payload = {
        "user_id": "12345",
        "email": "officer@bihar.gov.in",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "api_key": "live_key_987654321",
        "nested": {
            "secret_key": "nested_secret_value",
            "safe_property": "Khatian 105"
        }
    }
    redacted = redact_sensitive_data(raw_payload)

    assert redacted["password"] == "[REDACTED]"
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["secret_key"] == "[REDACTED]"
    assert redacted["nested"]["safe_property"] == "Khatian 105"
    assert redacted["email"] == "officer@bihar.gov.in"


def test_bearer_token_string_redaction():
    text = "User authenticated with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.header.sig successfully"
    redacted = redact_sensitive_data(text)
    assert "Bearer [REDACTED]" in redacted
    assert "eyJhbGci" not in redacted


def test_structured_json_formatter():
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="bhumisetu.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Login attempt with password MySecretPassword99",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    log_json = json.loads(formatted)
    assert log_json["level"] == "INFO"
    assert log_json["logger"] == "bhumisetu.test"
    assert "password [REDACTED]" in log_json["message"] or "[REDACTED]" in log_json["message"]


def test_readiness_probe_unready_when_redis_fails_under_async(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ASYNC_PROCESSING", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:65432/0")
    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unready"
    assert data["checks"]["redis"]["status"] == "unhealthy"


def test_readiness_probe_degraded_when_redis_fails_under_sync(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ASYNC_PROCESSING", False)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:65432/0")
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["redis"]["status"] == "unavailable"


def test_readiness_probe_unready_when_db_fails():
    from app.database import get_db
    class FailingDbSession:
        bind = None
        def execute(self, *args, **kwargs):
            raise Exception("Database connection refused")

    app.dependency_overrides[get_db] = lambda: FailingDbSession()
    try:
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unready"
        assert data["checks"]["database"]["status"] == "unhealthy"
    finally:
        app.dependency_overrides.pop(get_db, None)
