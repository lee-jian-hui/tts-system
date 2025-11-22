from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from .settings import get_engine, list_voices


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize (UTF-8, supports Korean)")
    voice: str | None = Field(None, description="Voice id or name")
    rate: float = Field(1.0, ge=0.5, le=2.0, description="Speech rate multiplier")
    pitch: float = Field(1.0, ge=0.5, le=2.0, description="Pitch multiplier")
    format: str = Field("wav", pattern=r"^(wav)$", description="Audio format")
    sample_rate: int = Field(22050, description="Output sample rate in Hz")


app = FastAPI(title="voice-tts-kr", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/voices")
def voices():
    return {"voices": list_voices()}


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    engine = get_engine()
    try:
        audio_bytes, sample_rate, mime = engine.synthesize(
            text=req.text,
            voice=req.voice,
            rate=req.rate,
            pitch=req.pitch,
            sample_rate=req.sample_rate,
            audio_format=req.format,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(content=audio_bytes, media_type=mime)

