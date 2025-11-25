from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import CreateTTSSessionRequest
from app.metrics import TTS_SESSION_QUEUE_FULL_TOTAL
from app.services.session_queue import SessionQueueFullError


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
    app = create_app()

    # Ensure both the API module and container return our stub service. Use
    # monkeypatch so the overrides are automatically restored after the test.
    monkeypatch.setattr("app.container.get_tts_service", lambda: stub)
    monkeypatch.setattr("app.api.get_tts_service", lambda: stub)

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


def _get_queue_full_events() -> float:
    for metric in TTS_SESSION_QUEUE_FULL_TOTAL.collect():
        for sample in metric.samples:
            if sample.name == "tts_session_queue_full_total":
                return float(sample.value)
    return 0.0


def test_websocket_stream_overload_returns_503_and_increments_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the streaming queue is full, the WS handler should return an error and increment the metric."""

    app = create_app()

    # Stub out enqueue_stream_request to simulate queue behaviour:
    # - First call: behave like a normal short stream (audio + eos).
    # - Second call: raise SessionQueueFullError to simulate overload.
    call_counter = {"n": 0}

    async def _fake_enqueue_stream_request(session_id, websocket, tts_service=None):
        from app.models import AudioChunkMessage, EndOfStreamMessage
        import base64

        call_counter["n"] += 1
        if call_counter["n"] == 1:
            # Simulate a tiny normal stream.
            data = base64.b64encode(b"\x00\x01").decode("ascii")
            msg = AudioChunkMessage(type="audio", seq=1, data=data)
            await websocket.send_json(msg.model_dump())
            eos = EndOfStreamMessage(type="eos")
            await websocket.send_json(eos.model_dump())
        else:
            # Simulate queue full: increment the metric and raise.
            TTS_SESSION_QUEUE_FULL_TOTAL.inc()
            raise SessionQueueFullError("session queue full (fake)")

    monkeypatch.setattr(
        "app.api.enqueue_stream_request", _fake_enqueue_stream_request
    )

    client = TestClient(app)

    payload = {
        "provider": "stub-provider",
        "voice": "stub-voice",
        "text": "Hello",
        "target_format": "pcm16",
        "sample_rate_hz": 16000,
        "language": "en-US",
    }

    # Create two sessions.
    resp1 = client.post("/v1/tts/sessions", json=payload)
    assert resp1.status_code == 201
    s1 = resp1.json()["session_id"]

    resp2 = client.post("/v1/tts/sessions", json=payload)
    assert resp2.status_code == 201
    s2 = resp2.json()["session_id"]

    before_queue_full = _get_queue_full_events()

    # First stream behaves normally.
    with client.websocket_connect(f"/v1/tts/stream/{s1}") as ws1:
        msg1 = ws1.receive_json()
        assert msg1["type"] == "audio"
        msg2 = ws1.receive_json()
        assert msg2["type"] == "eos"

    # Second stream should see an error due to "queue full".
    with client.websocket_connect(f"/v1/tts/stream/{s2}") as ws2:
        msg = ws2.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == 503
        assert "gateway overloaded" in msg["message"]

    after_queue_full = _get_queue_full_events()
    assert after_queue_full == before_queue_full + 1.0
