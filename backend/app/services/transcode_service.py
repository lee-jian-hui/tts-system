from __future__ import annotations

from enum import Enum

import subprocess
import asyncio

from app.models import AudioFormat
from app.providers import AudioChunk
from app.logging_utils import get_logger


logger = get_logger(__name__)


class SupportedAudioFormat(str, Enum):
    PCM16 = "pcm16"
    MULAW = "mulaw"
    OPUS = "opus"
    MP3 = "mp3"
    WAV = "wav"


class AudioTranscodeService:
    """General-purpose audio transcoder using ffmpeg CLI.

    This service accepts AudioChunk objects in any supported input
    format and transcodes them on the fly into the requested output
    format and sample rate.
    """

    async def transcode_chunk(
        self,
        chunk: AudioChunk,
        *,
        target_format: AudioFormat,
        sample_rate_hz: int,
    ) -> bytes:
        logger.info(
            "[START] transcode_chunk in=%s@%dHz ch=%d -> out=%s@%dHz (len=%d)",
            chunk.format,
            chunk.sample_rate_hz,
            chunk.num_channels,
            target_format,
            sample_rate_hz,
            len(chunk.data),
        )

        # Fast path: already in the requested format and sample rate.
        if chunk.format == target_format and chunk.sample_rate_hz == sample_rate_hz:
            logger.info("[SKIP] transcoding not required (format/rate match)")
            return chunk.data

        # Route all other cases through ffmpeg CLI.
        return await asyncio.to_thread(
            self._ffmpeg_transcode,
            data=chunk.data,
            in_format=chunk.format,
            in_rate=chunk.sample_rate_hz,
            in_channels=chunk.num_channels,
            out_format=target_format,
            out_rate=sample_rate_hz,
        )

    def _ffmpeg_transcode(
        self,
        *,
        data: bytes,
        in_format: AudioFormat,
        in_rate: int,
        in_channels: int,
        out_format: AudioFormat,
        out_rate: int,
    ) -> bytes:
        """Invoke ffmpeg CLI to convert between formats and sample rates."""

        def input_args(fmt: AudioFormat) -> list[str]:
            try:
                fmt_enum = SupportedAudioFormat(fmt)
            except ValueError as exc:  # invalid value for enum
                raise ValueError(f"Unsupported input format '{fmt}'") from exc

            if fmt_enum is SupportedAudioFormat.PCM16:
                return ["-f", "s16le", "-ar", str(in_rate), "-ac", str(in_channels)]
            if fmt_enum is SupportedAudioFormat.WAV:
                return ["-f", "wav", "-ar", str(in_rate), "-ac", str(in_channels)]
            if fmt_enum is SupportedAudioFormat.MP3:
                return ["-f", "mp3", "-ar", str(in_rate), "-ac", str(in_channels)]
            if fmt_enum is SupportedAudioFormat.MULAW:
                return ["-f", "mulaw", "-ar", str(in_rate), "-ac", str(in_channels)]
            if fmt_enum is SupportedAudioFormat.OPUS:
                return ["-f", "opus", "-ar", str(in_rate), "-ac", str(in_channels)]
            raise ValueError(f"Unsupported input format '{fmt}'")

        def output_args(fmt: AudioFormat) -> list[str]:
            try:
                fmt_enum = SupportedAudioFormat(fmt)
            except ValueError as exc:
                raise ValueError(f"Unsupported output format '{fmt}'") from exc

            if fmt_enum is SupportedAudioFormat.PCM16:
                return ["-f", "s16le", "-ar", str(out_rate), "-ac", str(in_channels)]
            if fmt_enum is SupportedAudioFormat.WAV:
                return ["-f", "wav", "-ar", str(out_rate), "-ac", str(in_channels)]
            if fmt_enum is SupportedAudioFormat.MP3:
                return [
                    "-f",
                    "mp3",
                    "-ar",
                    str(out_rate),
                    "-ac",
                    str(in_channels),
                    "-b:a",
                    "128k",
                ]
            if fmt_enum is SupportedAudioFormat.OPUS:
                return [
                    "-f",
                    "opus",
                    "-ar",
                    str(out_rate),
                    "-ac",
                    str(in_channels),
                    "-b:a",
                    "64k",
                ]
            if fmt_enum is SupportedAudioFormat.MULAW:
                return ["-f", "mulaw", "-ar", str(out_rate), "-ac", str(in_channels)]
            raise ValueError(f"Unsupported output format '{fmt}'")

        in_args = input_args(in_format)
        out_args = output_args(out_format)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            *in_args,
            "-i",
            "pipe:0",
            *out_args,
            "pipe:1",
        ]

        logger.info(
            "[FFMPEG] cmd=%s (input_len=%d)",
            " ".join(cmd),
            len(data),
        )

        try:
            proc = subprocess.run(
                cmd,
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            logger.error("ffmpeg execution failed: %s", exc, exc_info=True)
            raise ValueError(f"ffmpeg execution failed: {exc}") from exc

        if proc.returncode != 0:
            message = proc.stderr.decode("utf-8", errors="ignore") or str(
                proc.returncode
            )
            logger.error(
                "ffmpeg transcoding failed in=%s@%dHz ch=%d -> out=%s@%dHz: %s",
                in_format,
                in_rate,
                in_channels,
                out_format,
                out_rate,
                message,
            )
            raise ValueError(f"ffmpeg transcoding failed: {message}")

        out = proc.stdout or b""
        if not out:
            logger.error(
                "ffmpeg produced no output data in=%s@%dHz ch=%d -> out=%s@%dHz",
                in_format,
                in_rate,
                in_channels,
                out_format,
                out_rate,
            )
            raise ValueError("ffmpeg produced no output data")

        logger.info("[FFMPEG] produced %d bytes of audio data", len(out))
        return out
