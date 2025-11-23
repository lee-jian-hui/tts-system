from __future__ import annotations

import asyncio
from typing import AsyncIterator
from uuid import uuid4

from app.models import (
    CreateTTSSessionRequest,
    TTSSession,
    SessionStatus,
    AudioFormat,
)
from app.providers import ProviderRegistry
from app.repositories import TTSSessionRepository
from app import metrics as app_metrics
from .transcode_service import AudioTranscodeService
from .circuit_breaker import CircuitBreakerRegistry


class TTSService:
    """Orchestrates provider streaming and session lifecycle."""

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        session_repo: TTSSessionRepository,
        transcode_service: AudioTranscodeService,
        circuit_breakers: CircuitBreakerRegistry,
        provider_timeout_seconds: float = 10.0,
        provider_max_retries: int = 2,
    ) -> None:
        self._providers = provider_registry
        self._sessions = session_repo
        self._transcode = transcode_service
        self._circuit_breakers = circuit_breakers
        self._provider_timeout_seconds = provider_timeout_seconds
        self._provider_max_retries = max(1, provider_max_retries)

    def create_session(self, req: CreateTTSSessionRequest) -> TTSSession:
        """Create and persist a new TTS session."""
        session_id = str(uuid4())
        session = TTSSession.new(
            id=session_id,
            provider=req.provider,
            voice=req.voice,
            text=req.text,
            language=req.language,
            target_format=req.target_format,
            sample_rate_hz=req.sample_rate_hz,
        )
        self._sessions.save(session)
        app_metrics.record_session_created(req.provider)
        return session

    async def stream_session_audio(
        self,
        session_id: str,
    ) -> AsyncIterator[bytes]:
        """Yield encoded audio chunks for a given session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Unknown session '{session_id}'")

        provider_id = session.provider

        # Check circuit breaker before calling provider.
        if not self._circuit_breakers.allow_request(provider_id):
            raise ValueError(
                f"Provider '{provider_id}' temporarily unavailable (circuit open)"
            )

        provider = self._providers.get(provider_id)
        self._sessions.update_status(session.id, SessionStatus.STREAMING)
        app_metrics.increment_active_streams(provider_id)

        try:
            async for chunk in self._stream_from_provider_with_retry(
                provider_id=provider_id,
                provider=provider,
                text=session.text,
                voice_id=session.voice,
                language=session.language,
            ):
                encoded = await self._transcode.transcode_chunk(
                    chunk,
                    target_format=session.target_format,
                    sample_rate_hz=session.sample_rate_hz,
                )
                app_metrics.record_stream_chunk(
                    provider_id, session.target_format, len(encoded)
                )
                yield encoded
        except Exception:
            self._sessions.update_status(session.id, SessionStatus.FAILED)
            # Treat any failure during streaming as a provider failure event.
            self._circuit_breakers.record_failure(provider_id)
            app_metrics.record_session_failed(provider_id)
            app_metrics.record_provider_failure(provider_id)
            app_metrics.decrement_active_streams(provider_id)
            raise
        else:
            # Successful completion resets breaker state.
            self._circuit_breakers.record_success(provider_id)
            self._sessions.update_status(session.id, SessionStatus.COMPLETED)
            app_metrics.record_session_completed(provider_id)
            app_metrics.decrement_active_streams(provider_id)

    async def _stream_from_provider_with_retry(
        self,
        *,
        provider_id: str,
        provider,
        text: str,
        voice_id: str,
        language: str | None,
    ) -> AsyncIterator["AudioChunk"]:
        """Stream audio from provider with timeout and simple retry logic.

        If the provider fails or times out before yielding any audio, we will
        retry up to ``provider_max_retries`` times. Once audio has started
        flowing, any subsequent error ends the stream without retry to avoid
        duplicated audio.
        """

        from app.providers import AudioChunk  # local import to avoid cycle

        last_error: Exception | None = None
        for attempt in range(1, self._provider_max_retries + 1):
            had_output = False
            stream = provider.stream_synthesize(
                text=text,
                voice_id=voice_id,
                language=language,
            )
            try:
                while True:
                    try:
                        chunk: AudioChunk = await asyncio.wait_for(
                            stream.__anext__(),
                            timeout=self._provider_timeout_seconds,
                        )
                    except StopAsyncIteration:
                        return
                    had_output = True
                    yield chunk
            except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
                last_error = exc
                # If we already produced audio, do not retry to avoid duplicates.
                if had_output or attempt == self._provider_max_retries:
                    raise
                # Otherwise, fall through to next attempt in the loop.
                continue
