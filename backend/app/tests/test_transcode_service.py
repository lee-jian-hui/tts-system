from __future__ import annotations

import asyncio
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
