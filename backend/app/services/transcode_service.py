from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from app.models import AudioFormat
from app.providers import AudioChunk


class AudioTranscoder(ABC):
    """Abstract base class for audio transcoders.

    Implementations convert provider-produced audio chunks into a
    desired format and sample rate.
    """

    @abstractmethod
    async def transcode(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        """Convert an AudioChunk to the requested format/sample rate."""


class Pcm16Transcoder(AudioTranscoder):
    """PCM16 pass-through transcoder (MVP).

    Assumes input is PCM16 mono and returns the bytes unchanged when
    the requested target format is also PCM16 and the sample rate
    matches.
    """

    async def transcode(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        if target_format != "pcm16":
            raise ValueError("Pcm16Transcoder only supports 'pcm16' as target_format")
        if chunk.format != "pcm16":
            raise ValueError("Pcm16Transcoder expects input chunks in 'pcm16' format")
        if chunk.sample_rate_hz != sample_rate_hz:
            # Future work: resample when rates differ.
            raise ValueError("Sample rate mismatch in PCM16 transcoder")
        return chunk.data


class WavFromPcmTranscoder(AudioTranscoder):
    """Skeleton transcoder to wrap PCM16 data in a WAV container.

    This is intentionally left for future implementation. The typical
    steps will be:

    - Validate/convert input to PCM16.
    - Optionally resample to `sample_rate_hz`.
    - Use helpers from `app.audio` to construct a WAV header and
      prepend it to the PCM bytes.
    """

    async def transcode(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        # TODO: implement WAV wrapping logic based on app.audio helpers.
        raise NotImplementedError("WavFromPcmTranscoder not implemented yet")


class FfmpegTranscoder(AudioTranscoder):
    """Skeleton transcoder using ffmpeg for compressed formats.

    This is a placeholder for future work. A typical implementation
    would:

    - Accept PCM16 input.
    - Spawn an ffmpeg subprocess to convert PCM -> target_format.
    - Stream bytes in/out or buffer the full result.
    - Handle errors, timeouts, and non-zero exit codes.
    """

    async def transcode(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        # TODO: integrate ffmpeg or a Python audio library here.
        raise NotImplementedError("FfmpegTranscoder not implemented yet")


class AudioTranscodeService:
    """Route audio chunks through the appropriate transcoder.

    For MVP this only wires up a PCM16 pass-through transcoder. New
    formats (e.g., WAV, MP3, Opus) can be added by registering
    additional AudioTranscoder implementations.
    """

    def __init__(self) -> None:
        self._transcoders: Dict[AudioFormat, AudioTranscoder] = {
            "pcm16": Pcm16Transcoder(),
            # "wav": WavFromPcmTranscoder(),
            # "mp3": FfmpegTranscoder(),
            # "opus": FfmpegTranscoder(),
        }

    async def transcode_chunk(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        transcoder = self._transcoders.get(target_format)
        if transcoder is None:
            raise ValueError(f"Unsupported target_format '{target_format}'")
        return await transcoder.transcode(
            chunk,
            target_format=target_format,
            sample_rate_hz=sample_rate_hz,
        )
