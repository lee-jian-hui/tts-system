from __future__ import annotations

import asyncio

import pytest
from fastapi import WebSocket

from app.services.session_queue import (
  configure_session_queue,
  enqueue_stream_request,
  SessionQueueFullError,
  SessionWorkItem,
)
from app.services import TTSService
from app.providers import ProviderRegistry
from app.repositories import InMemoryTTSSessionRepository
from app.services.transcode_service import AudioTranscodeService
from app.services.circuit_breaker import CircuitBreakerRegistry
from app.models import CreateTTSSessionRequest


class _DummyWebSocket(WebSocket):  # type: ignore[misc]
  """Minimal WebSocket stub that just records sent JSON messages."""

  def __init__(self) -> None:
    # FastAPI's WebSocket expects a scope; we bypass most of it for tests.
    self.sent: list[dict] = []

  async def accept(self) -> None:  # type: ignore[override]
    return None

  async def send_json(self, data) -> None:  # type: ignore[override]
    self.sent.append(data)

  async def close(self, code: int = 1000, reason: str | None = None) -> None:  # type: ignore[override]
    self.sent.append({"type": "close", "code": code, "reason": reason})


def _build_tts_service() -> TTSService:
  registry = ProviderRegistry()
  repo = InMemoryTTSSessionRepository()
  transcode = AudioTranscodeService()
  breakers = CircuitBreakerRegistry()
  return TTSService(
    provider_registry=registry,
    session_repo=repo,
    transcode_service=transcode,
    circuit_breakers=breakers,
  )


def _make_request() -> CreateTTSSessionRequest:
  return CreateTTSSessionRequest(
    provider="mock_tone",
    voice="en-US-mock-1",
    text="hello",
    target_format="pcm16",
    sample_rate_hz=16000,
    language="en-US",
  )


@pytest.mark.asyncio
async def test_enqueue_stream_request_streams_when_queue_not_configured() -> None:
  """If the streaming queue is not configured, enqueue_stream_request should stream inline."""

  tts = _build_tts_service()
  req = _make_request()
  session = tts.create_session(req)

  ws = _DummyWebSocket()
  await enqueue_stream_request(session.id, ws, tts_service=tts)

  # We expect at least one audio message and a final eos.
  types = [m.get("type") for m in ws.sent]
  assert "audio" in types
  assert "eos" in types


@pytest.mark.asyncio
async def test_streaming_queue_limits_concurrency_and_depth() -> None:
  """Configure a very small streaming queue and ensure it enforces a hard limit."""

  tts = _build_tts_service()

  # Configure queue with maxsize=1 and worker_count=0 so that nothing drains
  # the queue; we will manually fill it to simulate "full".
  configure_session_queue(tts_service=tts, maxsize=1, worker_count=0)

  # Manually place one work item into the internal queue so that it is full.
  import app.services.session_queue as session_queue  # type: ignore[import]

  assert session_queue._queue is not None  # type: ignore[attr-defined]
  loop = asyncio.get_running_loop()
  fut = loop.create_future()
  await session_queue._queue.put(  # type: ignore[attr-defined]
    SessionWorkItem(session_id="s1", websocket=_DummyWebSocket(), future=fut)
  )

  # Now the next enqueue_stream_request should overflow the small queue and raise.
  ws2 = _DummyWebSocket()

  with pytest.raises(SessionQueueFullError):
    await enqueue_stream_request("s2", ws2, tts_service=tts)
