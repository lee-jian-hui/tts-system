from __future__ import annotations

from typing import List

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _run_single_flow(text: str) -> None:
    payload = {
        "provider": "mock_tone",
        "voice": "en-US-mock-1",
        "text": text,
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "en-US",
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


def test_e2e_mock_tone_multiple_utterances() -> None:
    for utterance in ["hi 1", "hi 2", "Hello KeyReply"]:
        _run_single_flow(utterance)

