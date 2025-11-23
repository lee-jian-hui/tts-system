from __future__ import annotations

import base64
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.models import (
    CreateTTSSessionRequest,
    CreateTTSSessionResponse,
    VoicesResponse,
    HealthResponse,
    AudioChunkMessage,
    EndOfStreamMessage,
    ErrorMessage,
    Voice,
)
from app.logging_utils import get_logger
from app.container import (
    get_provider_registry,
    get_session_repo,
    get_transcode_service,
    get_tts_service,
    get_rate_limiter,
)


logger = get_logger(__name__)


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


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    """Centralized logging for all HTTP requests."""
    import time

    start = time.monotonic()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration = time.monotonic() - start
        client_host = request.client.host if request.client else "unknown"
        status_code = response.status_code if response is not None else 500
        logger.info(
            "HTTP %s %s from %s -> %d in %.3fs",
            request.method,
            request.url.path,
            client_host,
            status_code,
            duration,
        )


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/v1/voices", response_model=VoicesResponse)
async def list_voices(
    provider: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
) -> VoicesResponse:
    registry = get_provider_registry()
    items: list[Voice] = []
    for p in registry.list_providers():
        if provider and p.id != provider:
            continue
        p_voices = await p.list_voices()
        for v in p_voices:
            if language and v.language != language:
                continue
            items.append(
                Voice(
                    id=v.id,
                    name=v.name,
                    language=v.language,
                    provider=p.id,
                    sample_rate_hz=v.sample_rate_hz,
                    supported_formats=["pcm16", "wav", "mp3"],
                )
            )
    return VoicesResponse(voices=items)


@app.post(
    "/v1/tts/sessions",
    response_model=CreateTTSSessionResponse,
    status_code=201,
)
async def create_session(
    req: CreateTTSSessionRequest,
    request: Request,
) -> CreateTTSSessionResponse:
    # Simple IP-based rate limiting for session creation.
    client_host = request.client.host if request.client else "unknown"
    limiter = get_rate_limiter()
    if not limiter.allow_request(client_host):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for this client",
        )

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
    payload = generate_latest()
    return PlainTextResponse(payload, media_type=CONTENT_TYPE_LATEST)


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
        # Unknown session or validation/transcoding error. Surface a structured
        # error message before closing the socket.
        logger.error(
            "WebSocket stream error for session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        err = ErrorMessage(type="error", code=400, message=str(exc))
        try:
            await websocket.send_json(err.dict())
        except Exception:
            # Best-effort; if sending the error fails, just close.
            pass
        await websocket.close(code=1011, reason=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        # Internal error; close with generic server error code.
        logger.error(
            "WebSocket internal error for session %s",
            session_id,
            exc_info=True,
        )
        err = ErrorMessage(type="error", code=500, message="internal error")
        try:
            await websocket.send_json(err.dict())
        except Exception:
            pass
        await websocket.close(code=1011, reason="internal error")
