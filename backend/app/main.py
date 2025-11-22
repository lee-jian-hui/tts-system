from __future__ import annotations

import base64
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.models import (
    CreateTTSSessionRequest,
    CreateTTSSessionResponse,
    VoicesResponse,
    HealthResponse,
    AudioChunkMessage,
    EndOfStreamMessage,
)
from app.container import (
    get_provider_registry,
    get_session_repo,
    get_transcode_service,
    get_tts_service,
    get_voice_repo,
)


app = FastAPI(title="tts-gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/v1/voices", response_model=VoicesResponse)
async def list_voices(
    provider: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
) -> VoicesResponse:
    voices = await get_voice_repo().list_voices(provider=provider, language=language)
    return VoicesResponse(voices=voices)


@app.post(
    "/v1/tts/sessions",
    response_model=CreateTTSSessionResponse,
    status_code=201,
)
async def create_session(
    req: CreateTTSSessionRequest,
    request: Request,
) -> CreateTTSSessionResponse:
    try:
        session = get_tts_service().create_session(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ws_url = str(request.url_for("stream_tts", session_id=session.id))
    # Switch to ws:// / wss:// scheme for WebSocket URL
    if ws_url.startswith("http://"):
        ws_url = "ws://" + ws_url[len("http://") :]
    elif ws_url.startswith("https://"):
        ws_url = "wss://" + ws_url[len("https://") :]

    return CreateTTSSessionResponse(session_id=session.id, ws_url=ws_url)


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    # Minimal stub; can be replaced with real Prometheus metrics.
    return PlainTextResponse("# metrics not implemented yet\n", media_type="text/plain")


@app.websocket("/v1/tts/stream/{session_id}")
async def stream_tts(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    tts_service = get_tts_service()
    seq = 1
    try:
        async for chunk in tts_service.stream_session_audio(session_id):
            b64 = base64.b64encode(chunk).decode("ascii")
            msg = AudioChunkMessage(type="audio", seq=seq, data=b64)
            await websocket.send_json(msg.dict())
            seq += 1
        eos = EndOfStreamMessage(type="eos")
        await websocket.send_json(eos.dict())
    except WebSocketDisconnect:
        # Client disconnected; nothing special to do.
        return
    except ValueError as exc:
        # Unknown session or validation error.
        await websocket.close(code=1008, reason=str(exc))
    except Exception:
        # Internal error; close with generic server error code.
        await websocket.close(code=1011)
