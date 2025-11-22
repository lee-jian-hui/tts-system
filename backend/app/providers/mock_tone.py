from __future__ import annotations

from typing import AsyncIterator

from .base import AudioChunk, BaseTTSProvider, ProviderVoice
from ..audio import pcm16le_from_floats, tone, silence


class MockToneProvider(BaseTTSProvider):
    """Mock provider that encodes text as a sequence of tones.

    This mirrors the existing DummyKoreanEngine behavior, but exposes
    a streaming interface that yields small PCM16 chunks instead of
    a single WAV blob.
    """

    id: str = "mock_tone"

    def __init__(self, sample_rate_hz: int = 16000) -> None:
        self._sample_rate_hz = sample_rate_hz
        self._voices: list[ProviderVoice] = [
            ProviderVoice(
                id="en-US-mock-1",
                name="Mock Tone Voice",
                language="en-US",
                sample_rate_hz=self._sample_rate_hz,
                base_format="pcm16",
            )
        ]

    async def list_voices(self) -> list[ProviderVoice]:
        return self._voices

    async def stream_synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        language: str | None = None,
    ) -> AsyncIterator[AudioChunk]:
        if not text:
            raise ValueError("text must not be empty")

        # For MVP, ignore voice_id/language validation beyond presence.
        sample_rate = self._sample_rate_hz

        base_freq = 220.0
        gain = 0.2
        char_ms = 80.0  # duration per character in ms
        gap_ms = 20.0   # gap between characters in ms

        samples: list[float] = []
        for ch in text:
            code = ord(ch)
            semitone = (code % 24) - 12
            freq = base_freq * (2 ** (semitone / 12.0))
            dur_s = char_ms / 1000.0
            gap_s = gap_ms / 1000.0
            samples.extend(tone(freq, dur_s, sample_rate, gain=gain))
            samples.extend(silence(gap_s, sample_rate))

        pcm = pcm16le_from_floats(samples)

        # Stream fixed-size chunks (~100ms of audio at 16kHz mono).
        bytes_per_second = sample_rate * 2  # 16-bit mono PCM
        chunk_duration_s = 0.1
        chunk_size = int(bytes_per_second * chunk_duration_s)
        if chunk_size <= 0:
            chunk_size = 1024

        for offset in range(0, len(pcm), chunk_size):
            chunk = pcm[offset : offset + chunk_size]
            if not chunk:
                break
            yield AudioChunk(
                data=chunk,
                sample_rate_hz=sample_rate,
                num_channels=1,
                format="pcm16",
            )

