from __future__ import annotations

import math
from typing import Tuple

from .base import BaseTTSEngine
from ..audio import join_wav, tone, silence


class DummyKoreanEngine(BaseTTSEngine):
    """A dependency-light, offline dummy engine.

    Encodes text as a sequence of tones derived from character code points.
    This is NOT real TTS, but lets us validate API/CLI and audio pipeline.
    """

    _voices = [
        {"id": "ko-neutral", "name": "Korean Neutral (Dummy)", "lang": "ko-KR"},
    ]

    def voices(self) -> list[dict]:
        return self._voices

    def synthesize(
        self,
        *,
        text: str,
        voice: str | None,
        rate: float,
        pitch: float,
        sample_rate: int,
        audio_format: str,
    ) -> Tuple[bytes, int, str]:
        if audio_format != "wav":
            raise ValueError("Only 'wav' format supported in dummy engine")
        if not text:
            raise ValueError("text must not be empty")

        # Map each character to a tone frequency in a pleasant-ish range
        # Base around 220Hz; spread by char code; mod into musical scale region.
        base = 220.0 * pitch
        gain = 0.2
        char_ms = max(40.0, 120.0 / rate)  # duration per char
        gap_ms = max(10.0, 30.0 / rate)    # small gap between chars

        samples: list[float] = []
        for ch in text:
            code = ord(ch)
            # Fold code into [0, 24) semitone steps
            semitone = (code % 24) - 12
            freq = base * (2 ** (semitone / 12.0))
            dur_s = char_ms / 1000.0
            gap_s = gap_ms / 1000.0
            samples.extend(tone(freq, dur_s, sample_rate, gain=gain))
            samples.extend(silence(gap_s, sample_rate))

        audio_bytes = join_wav(samples, sample_rate)
        return audio_bytes, sample_rate, "audio/wav"

