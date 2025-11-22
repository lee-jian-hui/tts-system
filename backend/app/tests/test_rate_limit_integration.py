from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.rate_limiter import RateLimitConfig, RateLimiter


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _valid_session_payload() -> dict:
    return {
        "provider": "mock_tone",
        "voice": "en-US-mock-1",
        "text": "Hello KeyReply",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "en-US",
    }


def test_create_session_is_rate_limited(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """POST /v1/tts/sessions should return 429 once the per-IP limit is exceeded."""

    cfg = RateLimitConfig(max_requests_per_window=2, window_seconds=60)
    limiter = RateLimiter(config=cfg)

    # Ensure the application uses our test-specific limiter instance.
    # The route imports get_rate_limiter directly from app.main.
    monkeypatch.setattr("app.main.get_rate_limiter", lambda: limiter)

    url = "/v1/tts/sessions"
    payload = _valid_session_payload()

    # First two requests should succeed.
    r1 = client.post(url, json=payload)
    assert r1.status_code == 201

    r2 = client.post(url, json=payload)
    assert r2.status_code == 201

    # Third request from the same client should be rejected with 429.
    r3 = client.post(url, json=payload)
    assert r3.status_code == 429
    assert "Rate limit exceeded" in r3.json().get("detail", "")
