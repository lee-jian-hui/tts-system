from __future__ import annotations

import asyncio

import pytest

from app.models import CreateTTSSessionRequest, SessionStatus
from app.providers import ProviderRegistry
from app.repositories import InMemoryTTSSessionRepository
from app.services import AudioTranscodeService, TTSService
from app.services.circuit_breaker import CircuitBreakerConfig, CircuitBreakerRegistry


def _build_tts_service() -> tuple[TTSService, InMemoryTTSSessionRepository]:
    registry = ProviderRegistry()
    repo = InMemoryTTSSessionRepository()
    transcode = AudioTranscodeService()
    breakers = CircuitBreakerRegistry()
    service = TTSService(
        provider_registry=registry,
        session_repo=repo,
        transcode_service=transcode,
        circuit_breakers=breakers,
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


class _FailingProvider:
    """Test provider that always fails when streaming."""

    id = "failing-provider"

    async def list_voices(self) -> list[object]:
        return []

    async def stream_synthesize(self, *, text: str, voice_id: str, language: str | None = None):  # type: ignore[override]  # noqa: E501
        raise RuntimeError("synthetic provider failure")


class _SingleProviderRegistry:
    """Minimal registry used for circuit breaker tests."""

    def __init__(self, provider: _FailingProvider) -> None:
        self._provider = provider

    def get(self, provider_id: str) -> _FailingProvider:
        if provider_id != self._provider.id:
            raise ValueError(f"Unknown provider '{provider_id}'")
        return self._provider

    def list_providers(self) -> list[_FailingProvider]:
        return [self._provider]


@pytest.mark.asyncio
async def test_stream_session_audio_trips_circuit_breaker_after_failures() -> None:
    """Repeated provider failures should open the circuit and block new streams."""

    # Configure a breaker that opens after two failures.
    breaker_cfg = CircuitBreakerConfig(failure_threshold=2, reset_timeout_seconds=60)
    breakers = CircuitBreakerRegistry(config=breaker_cfg)

    provider = _FailingProvider()
    registry = _SingleProviderRegistry(provider)
    repo = InMemoryTTSSessionRepository()
    transcode = AudioTranscodeService()

    service = TTSService(
        provider_registry=registry,  # type: ignore[arg-type]
        session_repo=repo,
        transcode_service=transcode,
        circuit_breakers=breakers,
    )

    def make_req() -> CreateTTSSessionRequest:
        return CreateTTSSessionRequest(
            provider=provider.id,
            voice="dummy-voice",
            text="Hello",
            target_format="pcm16",
            sample_rate_hz=16000,
            language="en-US",
        )

    # First two attempts should invoke the provider and fail.
    for _ in range(2):
        session = service.create_session(make_req())
        with pytest.raises(RuntimeError):
            async for _chunk in service.stream_session_audio(session.id):
                pass
        stored = repo.get(session.id)
        assert stored is not None
        assert stored.status == SessionStatus.FAILED

    # Third attempt should be rejected immediately by the circuit breaker.
    blocked_session = service.create_session(make_req())
    with pytest.raises(ValueError) as exc_info:
        async for _chunk in service.stream_session_audio(blocked_session.id):
            pass

    assert "temporarily unavailable" in str(exc_info.value)


class _SometimesSlowProvider:
    """Provider that times out on first attempt and succeeds on second."""

    id = "sometimes-slow"

    def __init__(self) -> None:
        self.calls = 0

    async def list_voices(self) -> list[object]:
        return []

    async def stream_synthesize(self, *, text: str, voice_id: str, language: str | None = None):  # type: ignore[override]  # noqa: E501
        self.calls += 1
        # First call never yields; second call yields a single tiny chunk.
        if self.calls == 1:
            while False:  # pragma: no cover - generator placeholder
                yield b""  # type: ignore[misc]
        else:
            from app.providers import AudioChunk

            yield AudioChunk(
                data=b"\x00\x01",
                sample_rate_hz=16000,
                num_channels=1,
                format="pcm16",  # type: ignore[arg-type]
            )


class _RegistryForSlowProvider:
    def __init__(self, provider: _SometimesSlowProvider) -> None:
        self._provider = provider

    def get(self, provider_id: str) -> _SometimesSlowProvider:
        if provider_id != self._provider.id:
            raise ValueError(f"Unknown provider '{provider_id}'")
        return self._provider

    def list_providers(self) -> list[_SometimesSlowProvider]:
        return [self._provider]


@pytest.mark.asyncio
async def test_stream_session_audio_retries_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the provider times out before producing audio, TTSService should retry."""

    slow_provider = _SometimesSlowProvider()
    registry = _RegistryForSlowProvider(slow_provider)
    repo = InMemoryTTSSessionRepository()
    transcode = AudioTranscodeService()
    breakers = CircuitBreakerRegistry()

    # Use small timeout and two attempts.
    service = TTSService(
        provider_registry=registry,  # type: ignore[arg-type]
        session_repo=repo,
        transcode_service=transcode,
        circuit_breakers=breakers,
        provider_timeout_seconds=0.01,
        provider_max_retries=2,
    )

    # Monkeypatch asyncio.wait_for so that the first call times out,
    # and the second call behaves normally.
    real_wait_for = asyncio.wait_for
    call_count = {"value": 0}

    async def fake_wait_for(awaitable, timeout=None):  # type: ignore[no-untyped-def]
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise asyncio.TimeoutError()
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr("app.services.tts_service.asyncio.wait_for", fake_wait_for)

    req = CreateTTSSessionRequest(
        provider=slow_provider.id,
        voice="dummy-voice",
        text="Hello",
        target_format="pcm16",
        sample_rate_hz=16000,
        language="en-US",
    )
    session = service.create_session(req)

    chunks: list[bytes] = []
    async for chunk in service.stream_session_audio(session.id):
        chunks.append(chunk)

    # We should have eventually received audio from the second attempt.
    assert len(chunks) == 1
    stored = repo.get(session.id)
    assert stored is not None
    assert stored.status == SessionStatus.COMPLETED
