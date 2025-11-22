from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


AudioFormat = Literal["pcm16", "mulaw", "opus", "mp3", "wav"]


class CreateTTSSessionRequest(BaseModel):
    """Request body for starting a new TTS streaming session."""

    provider: str = Field(..., description="Provider ID, e.g. 'mock_tone'")
    voice: str = Field(..., description="Voice ID within the provider")
    text: str = Field(..., min_length=1, description="Input text to synthesize")
    target_format: AudioFormat = Field(..., description="Desired output audio format")
    sample_rate_hz: int = Field(..., gt=0, description="Desired output sample rate")
    language: Optional[str] = Field(
        None, description="BCP-47 language tag, e.g. 'en-US'"
    )


class CreateTTSSessionResponse(BaseModel):
    session_id: str
    ws_url: str


class Voice(BaseModel):
    id: str
    name: str
    language: str
    provider: str
    sample_rate_hz: int
    supported_formats: List[AudioFormat]


class VoicesResponse(BaseModel):
    voices: List[Voice]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class AudioChunkMessage(BaseModel):
    type: Literal["audio"]
    seq: int
    data: bytes  # or base64 string if JSON encoding is used on the wire


class EndOfStreamMessage(BaseModel):
    type: Literal["eos"]

