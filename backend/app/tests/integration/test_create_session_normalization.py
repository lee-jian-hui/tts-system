from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_create_session_rejects_unknown_voice_for_provider(client: TestClient) -> None:
    payload = {
        "provider": "mock_tone",
        "voice": "non-existent-voice",
        "text": "Hello",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "en-US",
    }

    resp = client.post("/v1/tts/sessions", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert "unknown voice" in body["detail"]


def test_create_session_rejects_mismatched_language_for_voice(
    client: TestClient,
) -> None:
    # mock_tone voice language is en-US; provide different language.
    payload = {
        "provider": "mock_tone",
        "voice": "en-US-mock-1",
        "text": "Hello",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "fr-FR",
    }

    resp = client.post("/v1/tts/sessions", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert "not supported by voice" in body["detail"]


def test_create_session_defaults_language_from_voice_when_missing(
    client: TestClient,
) -> None:
    payload = {
        "provider": "mock_tone",
        "voice": "en-US-mock-1",
        "text": "Hello",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
    }

    resp = client.post("/v1/tts/sessions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data

