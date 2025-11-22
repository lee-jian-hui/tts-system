from __future__ import annotations

import io
import subprocess
import wave
from typing import Any, Dict

import pytest

from app.providers import AudioChunk
from app.services import AudioTranscodeService


@pytest.mark.asyncio
async def test_transcode_pass_through_when_format_and_rate_match() -> None:
    """If input and output formats + rates match, bytes are returned unchanged."""
    data = b"\x01\x02\x03\x04"
    chunk = AudioChunk(data=data, sample_rate_hz=16000, num_channels=1, format="pcm16")
    service = AudioTranscodeService()

    out = await service.transcode_chunk(
        chunk,
        target_format="pcm16",  # type: ignore[arg-type]
        sample_rate_hz=16000,
    )

    assert out == data


@pytest.mark.asyncio
async def test_transcode_uses_ffmpeg_when_rate_differs(monkeypatch: pytest.MonkeyPatch) -> None:
    """When sample rate differs, service should delegate to _ffmpeg_transcode."""
    chunk = AudioChunk(
        data=b"\x00" * 160,
        sample_rate_hz=8000,
        num_channels=1,
        format="pcm16",
    )
    service = AudioTranscodeService()

    called: Dict[str, Any] = {}

    def fake_ffmpeg_transcode(self, **kwargs: Any) -> bytes:  # type: ignore[no-untyped-def]
        called.update(kwargs)
        return b"resampled"

    monkeypatch.setattr(
        AudioTranscodeService,
        "_ffmpeg_transcode",
        fake_ffmpeg_transcode,
        raising=True,
    )

    out = await service.transcode_chunk(
        chunk,
        target_format="pcm16",  # type: ignore[arg-type]
        sample_rate_hz=16000,
    )

    assert out == b"resampled"
    assert called["data"] == chunk.data
    assert called["in_format"] == "pcm16"
    assert called["out_format"] == "pcm16"
    assert called["in_rate"] == 8000
    assert called["out_rate"] == 16000
    assert called["in_channels"] == 1


@pytest.mark.asyncio
async def test_transcode_rejects_unsupported_input_format() -> None:
    """Unknown input format should raise a clear error."""
    data = b"\x01\x02"
    # type: ignore[arg-type] to force an unsupported format for the test.
    chunk = AudioChunk(data=data, sample_rate_hz=16000, num_channels=1, format="unknown")  # type: ignore[arg-type]
    service = AudioTranscodeService()

    with pytest.raises(ValueError) as exc_info:
        await service.transcode_chunk(
            chunk,
            target_format="pcm16",  # type: ignore[arg-type]
            sample_rate_hz=16000,
        )

    assert "Unsupported input format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcode_rejects_unsupported_output_format() -> None:
    """Unknown output format should raise a clear error."""
    data = b"\x01\x02"
    chunk = AudioChunk(data=data, sample_rate_hz=16000, num_channels=1, format="pcm16")
    service = AudioTranscodeService()

    with pytest.raises(ValueError) as exc_info:
        await service.transcode_chunk(
            chunk,
            target_format="ogg",  # type: ignore[arg-type]
            sample_rate_hz=16000,
        )

    assert "Unsupported output format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcode_to_wav_produces_valid_wav_header() -> None:
    """Transcoding PCM16 to WAV should produce a parseable WAV file."""
    # Simple 160-sample PCM16 mono chunk at 16 kHz.
    pcm_data = b"\x00\x01" * 80
    chunk = AudioChunk(
        data=pcm_data,
        sample_rate_hz=16000,
        num_channels=1,
        format="pcm16",
    )
    service = AudioTranscodeService()

    wav_bytes = await service.transcode_chunk(
        chunk,
        target_format="wav",  # type: ignore[arg-type]
        sample_rate_hz=16000,
    )

    # Basic header checks.
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes[8:16]

    # Use the wave module to ensure Python can parse it.
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getnframes() > 0


@pytest.mark.asyncio
async def test_transcode_to_mp3_produces_decodable_audio() -> None:
    """Transcoding PCM16 to MP3 should yield bytes that ffmpeg can decode."""
    pcm_data = b"\x00\x01" * 800  # a bit more data to make MP3 meaningful
    chunk = AudioChunk(
        data=pcm_data,
        sample_rate_hz=16000,
        num_channels=1,
        format="pcm16",
    )
    service = AudioTranscodeService()

    mp3_bytes = await service.transcode_chunk(
        chunk,
        target_format="mp3",  # type: ignore[arg-type]
        sample_rate_hz=16000,
    )

    assert mp3_bytes
    # The output should not be identical to the raw PCM input.
    assert mp3_bytes != pcm_data

    # Use ffmpeg CLI to decode the MP3 back to PCM; if ffmpeg succeeds and
    # produces some output, we treat that as verification the MP3 is valid.
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "mp3",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "pipe:1",
        ],
        input=mp3_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="ignore")
    assert proc.stdout
