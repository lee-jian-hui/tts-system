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


def _run_single_flow(
    *,
    text: str,
    target_format: str,
    sample_rate_hz: int,
    voice: str,
    language: str,
) -> None:
    # Use a sample rate close to the model's native rate (22050Hz) to
    # keep transcoding overhead modest in integration tests.
    payload = {
        "provider": "coqui_tts",
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
@pytest.mark.parametrize(
    "target_format,sample_rate_hz,voice,language",
    [
        ("pcm16", 22050, "coqui-en-1", "en-US"),
        ("wav", 22050, "coqui-en-1", "en-US"),
        ("mp3", 16000, "coqui-en-1", "en-US"),
    ],
)
def test_e2e_coqui_tts_multiple_formats_and_utterances(
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
