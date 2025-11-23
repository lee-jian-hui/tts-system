from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CreateTTSSessionRequest


class _SequencingTestTTSService:
    """Minimal TTS service stub that yields a fixed number of chunks."""

    def __init__(self) -> None:
        self._next_session_id = 1

    def create_session(self, req: CreateTTSSessionRequest):
        class _Session:
            def __init__(self, sid: str) -> None:
                self.id = sid

        sid = f"test-session-{self._next_session_id}"
        self._next_session_id += 1
        return _Session(sid)

    async def stream_session_audio(self, session_id: str) -> AsyncIterator[bytes]:
        for _ in range(3):
            await asyncio.sleep(0)
            yield b"\x00\x01"


@pytest.fixture
def client_with_sequencing_stub(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    stub = _SequencingTestTTSService()
    monkeypatch.setattr("app.main.get_tts_service", lambda: stub)
    return TestClient(app)


def test_websocket_chunk_sequencing_is_strictly_incremental(
    client_with_sequencing_stub: TestClient,
) -> None:
    client = client_with_sequencing_stub

    payload = {
        "provider": "stub-provider",
        "voice": "stub-voice",
        "text": "Hello",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "en-US",
    }

    resp = client.post("/v1/tts/sessions", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    session_id = data["session_id"]

    with client.websocket_connect(f"/v1/tts/stream/{session_id}") as ws:
        expected_seq = 1
        while True:
            msg = ws.receive_json()
            msg_type = msg.get("type")
            if msg_type == "audio":
                assert msg["seq"] == expected_seq
                expected_seq += 1
            elif msg_type == "eos":
                break
            else:
                pytest.fail(f"Unexpected message type {msg_type!r}")

        assert expected_seq == 4

