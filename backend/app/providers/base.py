from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Literal, Protocol


AudioFormat = Literal["pcm16", "mulaw", "opus", "mp3", "wav"]


@dataclass
class ProviderVoice:
    """Metadata for a single voice exposed by a provider."""

    id: str
    name: str
    language: str
    sample_rate_hz: int
    base_format: AudioFormat = "pcm16"


@dataclass
class AudioChunk:
    """A chunk of raw audio produced by a provider.

    The gateway is responsible for re-encoding this into the requested
    target format and wrapping it in any transport-specific envelope.
    """

    data: bytes
    sample_rate_hz: int
    num_channels: int = 1
    format: AudioFormat = "pcm16"


class BaseTTSProvider(Protocol):
    """Interface for TTS providers that stream audio chunks."""

    id: str

    async def list_voices(self) -> list[ProviderVoice]:
        """Return the voices supported by this provider."""

    async def stream_synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        language: str | None = None,
    ) -> AsyncIterator[AudioChunk]:
        """Stream audio chunks for the given synthesis request."""

