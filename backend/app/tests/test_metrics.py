from __future__ import annotations

from typing import Optional

from fastapi.testclient import TestClient

from app.main import app
from app.metrics import TTS_SESSIONS_TOTAL


def _get_sessions_metric_value(provider: str, status: str) -> float:
    """Helper to read the current value of tts_sessions_total for labels."""
    for metric in TTS_SESSIONS_TOTAL.collect():
        for sample in metric.samples:
            if (
                sample.name == "tts_sessions_total"
                and sample.labels.get("provider") == provider
                and sample.labels.get("status") == status
            ):
                return float(sample.value)
    return 0.0


def test_metrics_endpoint_exposes_prometheus_metrics() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert content_type.startswith("text/plain")
    body = response.text
    # At minimum, our custom counter name should be present.
    assert "tts_sessions_total" in body


def test_create_session_updates_sessions_metric() -> None:
    client = TestClient(app)

    provider = "mock_tone"
    status = "created"

    before = _get_sessions_metric_value(provider, status)

    payload = {
        "provider": provider,
        "voice": "en-US-mock-1",
        "text": "Hello KeyReply",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "en-US",
    }

    response = client.post("/v1/tts/sessions", json=payload)
    assert response.status_code == 201

    after = _get_sessions_metric_value(provider, status)
    assert after == before + 1.0

