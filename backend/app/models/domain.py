from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .audio_format import AudioFormat


class SessionStatus(Enum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TTSSession:
    """Domain model representing a TTS streaming session."""

    id: str
    provider: str
    voice: str
    text: str
    language: Optional[str]
    target_format: AudioFormat
    sample_rate_hz: int
    created_at: datetime
    status: SessionStatus = SessionStatus.PENDING

    @classmethod
    def new(
        cls,
        *,
        id: str,
        provider: str,
        voice: str,
        text: str,
        language: Optional[str],
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> "TTSSession":
        return cls(
            id=id,
            provider=provider,
            voice=voice,
            text=text,
            language=language,
            target_format=target_format,
            sample_rate_hz=sample_rate_hz,
            created_at=datetime.now(timezone.utc),
            status=SessionStatus.PENDING,
        )
