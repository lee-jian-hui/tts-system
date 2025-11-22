from __future__ import annotations

from voice_tts_kr.models import AudioFormat
from voice_tts_kr.providers import AudioChunk


class AudioTranscodeService:
    """Minimal audio transcoder.

    For MVP this is a pass-through for pcm16. It is structured so
    that it can later wrap ffmpeg or another library to support
    additional formats.
    """

    async def transcode_chunk(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        if target_format != "pcm16":
            # Future work: integrate ffmpeg to support more formats.
            raise ValueError("Only 'pcm16' target_format is supported in MVP")
        if chunk.sample_rate_hz != sample_rate_hz:
            # Future work: resample when rates differ.
            # For now we assume provider sample rate matches requested.
            raise ValueError("Sample rate mismatch in MVP transcoder")
        return chunk.data

