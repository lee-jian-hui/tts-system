from __future__ import annotations

from typing import List

import pytest
from fastapi.testclient import TestClient

from app.main import app

try:
    # Coqui TTS must be installed and configured for this test to run.
    from TTS.api import TTS as _CoquiTTS  # type: ignore[import]

    COQUI_AVAILABLE = True
except Exception:  # pragma: no cover - environment dependent
    COQUI_AVAILABLE = False


client = TestClient(app)



# TODO: implement more tests for each output format
# TODO: implement a DO-ALL test case that iterates across all possible provider and all possible voice and format
def _run_single_flow(text: str) -> None:
    # Use 22050Hz to match common Coqui output rate and avoid
    # unnecessary transcoding work in this integration test.
    payload = {
        "provider": "coqui_tts",
        "voice": "coqui-en-1",
        "text": text,
        "target_format": "pcm16",
        "sample_rate_hz": 22050,
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
                total_bytes += len(msg["data"])
            elif msg["type"] == "eos":
                eos_seen = True
                break

    assert eos_seen, "Expected EOS message at end of stream"
    assert audio_messages, "Expected at least one audio message"
    assert total_bytes > 0, "Expected some audio payload bytes"


@pytest.mark.skipif(
    not COQUI_AVAILABLE,
    reason="Coqui TTS library not available; install 'TTS' to run this test.",
)
def test_e2e_coqui_tts_multiple_utterances() -> None:
    for utterance in ["hi 1", "hi 2", "Hello KeyReply"]:
        _run_single_flow(utterance)

