from __future__ import annotations

from typing import List

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app())


def _run_single_flow(
    *,
    text: str,
    target_format: str,
    sample_rate_hz: int,
    voice: str,
    language: str,
) -> None:
    payload = {
        "provider": "mock_tone",
        "voice": voice,
        "text": text,
        "target_format": target_format,
        "sample_rate_hz": sample_rate_hz,
        "language": language,
    }

    # 1) Create session
    resp = client.post("/v1/tts/sessions", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    session_id = body["session_id"]
    assert isinstance(session_id, str) and session_id

    # 2) Stream over WebSocket
    total_bytes = 0
    audio_messages: List[dict] = []
    eos_seen = False

    with client.websocket_connect(f"/v1/tts/stream/{session_id}") as ws:
        while True:
            msg = ws.receive_json()
            if msg["type"] == "audio":
                audio_messages.append(msg)
                # data is base64-encoded string; just accumulate length
                total_bytes += len(msg["data"])
            elif msg["type"] == "eos":
                eos_seen = True
                break

    assert eos_seen, "Expected EOS message at end of stream"
    assert audio_messages, "Expected at least one audio message"
    assert total_bytes > 0, "Expected some audio payload bytes"


@pytest.mark.parametrize(
    "target_format,sample_rate_hz,voice,language",
    [
        ("pcm16", 16000, "en-US-mock-1", "en-US"),
        ("wav", 16000, "en-US-mock-1", "en-US"),
        ("mp3", 16000, "en-US-mock-1", "en-US"),
    ],
)
def test_e2e_mock_tone_multiple_formats_and_utterances(
    target_format: str,
    sample_rate_hz: int,
    voice: str,
    language: str,
) -> None:
    for utterance in ["hi 1", "hi 2", "Hello KeyReply"]:
        _run_single_flow(
            text=utterance,
            target_format=target_format,
            sample_rate_hz=sample_rate_hz,
            voice=voice,
            language=language,
        )
