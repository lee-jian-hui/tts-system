from __future__ import annotations

import math
import struct
from typing import Iterable


def pcm16le_from_floats(samples: Iterable[float]) -> bytes:
    # Clamp and convert [-1.0, 1.0] floats to 16-bit little-endian PCM
    out = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, float(s)))
        iv = int(round(v * 32767.0))
        out += struct.pack('<h', iv)
    return bytes(out)


def wav_header(num_samples: int, sample_rate: int, num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align
    riff_size = 36 + data_size
    return struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        riff_size,
        b'WAVE',
        b'fmt ',
        16,  # Subchunk1Size for PCM
        1,   # AudioFormat PCM
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size,
    )


def join_wav(samples: Iterable[float], sample_rate: int) -> bytes:
    pcm = pcm16le_from_floats(samples)
    header = wav_header(num_samples=len(pcm) // 2, sample_rate=sample_rate)
    return header + pcm


def tone(frequency: float, duration_s: float, sample_rate: int, gain: float = 0.2) -> list[float]:
    n = int(duration_s * sample_rate)
    two_pi_f = 2.0 * math.pi * frequency
    out = [math.sin(two_pi_f * (i / sample_rate)) * gain for i in range(n)]
    return out


def silence(duration_s: float, sample_rate: int) -> list[float]:
    n = int(duration_s * sample_rate)
    return [0.0] * n

