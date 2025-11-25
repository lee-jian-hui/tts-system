from __future__ import annotations

import asyncio

import pytest
from fastapi import WebSocket

from app.services.session_queue import (
  configure_session_queue,
  enqueue_stream_request,
  SessionQueueFullError,
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
  # the queue; this makes QueueFull deterministic for the test.
  configure_session_queue(tts_service=tts, maxsize=1, worker_count=0)

  # Create two sessions; the second enqueue should fail once the queue is full.
  req1 = _make_request()
  s1 = tts.create_session(req1)
  req2 = _make_request()
  s2 = tts.create_session(req2)

  ws1 = _DummyWebSocket()
  ws2 = _DummyWebSocket()

  # First request should be accepted into the queue.
  await enqueue_stream_request(s1.id, ws1, tts_service=tts)

  # Second request should overflow the small queue and raise.
  with pytest.raises(SessionQueueFullError):
    await enqueue_stream_request(s2.id, ws2, tts_service=tts)
