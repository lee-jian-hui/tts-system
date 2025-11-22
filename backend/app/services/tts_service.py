from __future__ import annotations

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
from .transcode_service import AudioTranscodeService


class TTSService:
    """Orchestrates provider streaming and session lifecycle."""

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        session_repo: TTSSessionRepository,
        transcode_service: AudioTranscodeService,
    ) -> None:
        self._providers = provider_registry
        self._sessions = session_repo
        self._transcode = transcode_service

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
        return session

    async def stream_session_audio(
        self,
        session_id: str,
    ) -> AsyncIterator[bytes]:
        """Yield encoded audio chunks for a given session."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Unknown session '{session_id}'")

        provider = self._providers.get(session.provider)
        self._sessions.update_status(session.id, SessionStatus.STREAMING)

        try:
            async for chunk in provider.stream_synthesize(
                text=session.text,
                voice_id=session.voice,
                language=session.language,
            ):
                encoded = await self._transcode.transcode_chunk(
                    chunk,
                    target_format=session.target_format,
                    sample_rate_hz=session.sample_rate_hz,
                )
                yield encoded
        except Exception:
            self._sessions.update_status(session.id, SessionStatus.FAILED)
            raise
        else:
            self._sessions.update_status(session.id, SessionStatus.COMPLETED)
