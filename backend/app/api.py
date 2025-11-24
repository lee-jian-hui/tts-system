from __future__ import annotations

import base64
from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import PlainTextResponse, Response
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
    get_tts_service,
    get_rate_limiter,
    get_session_repo,
    get_transcode_service,
)
from app.providers import AudioChunk as ProviderAudioChunk


logger = get_logger(__name__)
router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def root() -> PlainTextResponse:
    """Simple root endpoint for quick sanity checks."""
    return PlainTextResponse("hi there from KeyReply", media_type="text/plain")


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/v1/voices", response_model=VoicesResponse)
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


@router.post(
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

    from app.container import get_tts_service  # local to avoid cycles

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


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    payload = generate_latest()
    return PlainTextResponse(payload, media_type=CONTENT_TYPE_LATEST)


@router.websocket("/v1/tts/stream/{session_id}")
async def stream_tts(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    tts_service = get_tts_service()
    seq = 1
    try:
        async for chunk in tts_service.stream_session_audio(session_id):
            b64 = base64.b64encode(chunk).decode("ascii")
            msg = AudioChunkMessage(type="audio", seq=seq, data=b64)
            await websocket.send_json(msg.model_dump())
            seq += 1
        eos = EndOfStreamMessage(type="eos")
        await websocket.send_json(eos.model_dump())
    except WebSocketDisconnect:
        # Client disconnected; nothing special to do.
        return
    except ValueError as exc:
        # Unknown session or validation/transcoding error.
        logger.error(
            "WebSocket stream error for session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        err = ErrorMessage(type="error", code=400, message=str(exc))
        try:
            await websocket.send_json(err.model_dump())
        except Exception:
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
            await websocket.send_json(err.model_dump())
        except Exception:
            pass
        await websocket.close(code=1011, reason="internal error")


@router.get("/v1/tts/sessions/{session_id}/file")
async def get_session_file(
    session_id: str,
    format: Optional[str] = None,
) -> Response:
    """Return a full audio file for a completed session.

    This endpoint is intended for container formats (wav/mp3) where the frontend
    expects a single valid file rather than concatenated per-chunk encodings.
    Internally, we re-run provider synthesis to obtain the audio and then
    transcode it once into the requested format.
    """

    sessions = get_session_repo()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Unknown session '{session_id}'")

    target_format = format or session.target_format

    registry = get_provider_registry()
    provider = registry.get(session.provider)

    pcm_buf = bytearray()
    sample_rate = None
    num_channels = 1

    async for chunk in provider.stream_synthesize(
        text=session.text,
        voice_id=session.voice,
        language=session.language,
    ):
        if sample_rate is None:
            sample_rate = chunk.sample_rate_hz
            num_channels = chunk.num_channels
        pcm_buf.extend(chunk.data)

    if sample_rate is None:
        raise HTTPException(status_code=500, detail="Provider produced no audio data")

    full_chunk = ProviderAudioChunk(
        data=bytes(pcm_buf),
        sample_rate_hz=sample_rate,
        num_channels=num_channels,
        format="pcm16",
    )

    encoded = await get_transcode_service().transcode_chunk(
        full_chunk,
        target_format=target_format,  # type: ignore[arg-type]
        sample_rate_hz=session.sample_rate_hz,
    )

    if target_format == "mp3":
        media_type = "audio/mpeg"
    elif target_format == "wav":
        media_type = "audio/wav"
    else:
        media_type = "application/octet-stream"

    return Response(content=encoded, media_type=media_type)
