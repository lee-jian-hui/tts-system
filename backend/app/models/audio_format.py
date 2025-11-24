from __future__ import annotations

from enum import Enum


class AudioFormat(str, Enum):
    PCM16 = "pcm16"
    MULAW = "mulaw"
    OPUS = "opus"
    MP3 = "mp3"
    WAV = "wav"

