from __future__ import annotations

import pytest

from app.models import CreateTTSSessionRequest, SessionStatus
from app.providers import ProviderRegistry
from app.repositories import InMemoryTTSSessionRepository
from app.services import AudioTranscodeService, TTSService


def _build_tts_service() -> tuple[TTSService, InMemoryTTSSessionRepository]:
    registry = ProviderRegistry()
    repo = InMemoryTTSSessionRepository()
    transcode = AudioTranscodeService()
    service = TTSService(
        provider_registry=registry,
        session_repo=repo,
        transcode_service=transcode,
    )
    return service, repo


def _make_request() -> CreateTTSSessionRequest:
    return CreateTTSSessionRequest(
        provider="mock_tone",
        voice="en-US-mock-1",
        text="Hello KeyReply",
        target_format="pcm16",
        sample_rate_hz=16000,
        language="en-US",
    )


def test_create_session_persists_session() -> None:
    service, repo = _build_tts_service()

    req = _make_request()
    session = service.create_session(req)

    stored = repo.get(session.id)
    assert stored is not None
    assert stored.text == "Hello KeyReply"
    assert stored.status == SessionStatus.PENDING


@pytest.mark.asyncio
async def test_stream_session_audio_yields_bytes_and_updates_status() -> None:
    service, repo = _build_tts_service()

    req = _make_request()
    session = service.create_session(req)

    chunks: list[bytes] = []
    async for chunk in service.stream_session_audio(session.id):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert all(isinstance(c, (bytes, bytearray)) for c in chunks)

    stored = repo.get(session.id)
    assert stored is not None
    assert stored.status == SessionStatus.COMPLETED


@pytest.mark.asyncio
async def test_stream_session_audio_unknown_session_raises() -> None:
    service, _ = _build_tts_service()

    with pytest.raises(ValueError) as exc_info:
        async for _ in service.stream_session_audio("does-not-exist"):
            pass

    assert "Unknown session" in str(exc_info.value)
