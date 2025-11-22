from __future__ import annotations

import pytest

from app.providers import AudioChunk
from app.services import AudioTranscodeService


@pytest.mark.asyncio
async def test_transcode_pass_through_pcm16() -> None:
    data = b"\x01\x02\x03\x04"
    chunk = AudioChunk(data=data, sample_rate_hz=16000)
    service = AudioTranscodeService()

    out = await service.transcode_chunk(
        chunk,
        target_format="pcm16",  # type: ignore[arg-type]
        sample_rate_hz=16000,
    )

    assert out == data


@pytest.mark.asyncio
async def test_transcode_rejects_unsupported_format() -> None:
    data = b"\x01\x02"
    chunk = AudioChunk(data=data, sample_rate_hz=16000)
    service = AudioTranscodeService()

    with pytest.raises(ValueError) as exc_info:
        await service.transcode_chunk(
            chunk,
            target_format="wav",  # type: ignore[arg-type]
            sample_rate_hz=16000,
        )

    assert "Unsupported target_format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcode_rejects_sample_rate_mismatch() -> None:
    data = b"\x01\x02"
    chunk = AudioChunk(data=data, sample_rate_hz=8000)
    service = AudioTranscodeService()

    with pytest.raises(ValueError) as exc_info:
        await service.transcode_chunk(
            chunk,
            target_format="pcm16",  # type: ignore[arg-type]
            sample_rate_hz=16000,
        )

    assert "Sample rate mismatch" in str(exc_info.value)
