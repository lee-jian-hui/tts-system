from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.metrics import TTS_SESSIONS_TOTAL
from app.services.rate_limiter import RateLimitConfig, RateLimiter


@pytest.fixture
def client() -> TestClient:
    app = create_app()
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


def _get_sessions_metric_value(provider: str, status: str) -> float:
    for metric in TTS_SESSIONS_TOTAL.collect():
        for sample in metric.samples:
            if (
                sample.name == "tts_sessions_total"
                and sample.labels.get("provider") == provider
                and sample.labels.get("status") == status
            ):
                return float(sample.value)
    return 0.0


def test_http_logging_middleware_logs_request(caplog, client: TestClient) -> None:
    with caplog.at_level(logging.INFO):
        response = client.get("/healthz")

    assert response.status_code == 200
    messages = [record.getMessage() for record in caplog.records]
    assert any("HTTP GET /healthz" in msg for msg in messages)


def test_metrics_endpoint_exposes_prometheus_metrics(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/plain")
    body = response.text
    assert "tts_sessions_total" in body


def test_create_session_updates_sessions_metric(client: TestClient) -> None:
    provider = "mock_tone"
    status = "created"

    before = _get_sessions_metric_value(provider, status)

    payload = _valid_session_payload()

    response = client.post("/v1/tts/sessions", json=payload)
    assert response.status_code == 201

    after = _get_sessions_metric_value(provider, status)
    assert after == before + 1.0


def test_create_session_is_rate_limited(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    cfg = RateLimitConfig(max_requests_per_window=2, window_seconds=60)
    limiter = RateLimiter(config=cfg)

    # Monkeypatch the container-level limiter used by the router.
    from app import container

    container.get_rate_limiter.cache_clear()
    container.get_rate_limiter = lambda: limiter  # type: ignore[assignment]

    url = "/v1/tts/sessions"
    payload = _valid_session_payload()

    r1 = client.post(url, json=payload)
    assert r1.status_code == 201

    r2 = client.post(url, json=payload)
    assert r2.status_code == 201

    r3 = client.post(url, json=payload)
    assert r3.status_code == 429
    assert "Rate limit exceeded" in r3.json().get("detail", "")
