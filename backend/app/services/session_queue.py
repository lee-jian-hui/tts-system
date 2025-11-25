from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
import base64

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.logging_utils import get_logger
from app.models import AudioChunkMessage, EndOfStreamMessage, ErrorMessage
from app.services import TTSService
from app import metrics as app_metrics


logger = get_logger(__name__)


@dataclass
class SessionWorkItem:
    """Work item for the streaming queue."""

    session_id: str
    websocket: WebSocket
    future: asyncio.Future[None]


class SessionQueueFullError(RuntimeError):
    """Raised when the session queue is at capacity."""


_queue: Optional[asyncio.Queue[SessionWorkItem]] = None
_workers_started = False
_workers_busy = 0


def configure_session_queue(
    *,
    tts_service: TTSService,
    maxsize: int,
    worker_count: int,
) -> None:
    """Configure the global in-process streaming queue and start worker tasks.

    This provides a bounded-queue + worker-pool mechanism for handling
    *streaming* work (provider synthesis + transcoding + WebSocket sends),
    rather than the cheap `create_session` step. It lets the gateway smooth
    bursts of streaming requests while still enforcing an upper bound on how
    many streams can be active or queued in memory.
    """
    global _queue, _workers_started

    if _workers_started:
        return

    loop = asyncio.get_event_loop()
    _queue = asyncio.Queue[SessionWorkItem](maxsize=maxsize)
    app_metrics.TTS_SESSION_QUEUE_MAXSIZE.set(maxsize)
    app_metrics.TTS_SESSION_WORKERS_TOTAL.set(worker_count)

    async def worker(worker_id: int) -> None:
        assert _queue is not None
        logger.info(
            "Session streaming worker %d starting (maxsize=%d)",
            worker_id,
            maxsize,
        )
        global _workers_busy
        while True:
            item = await _queue.get()
            try:
                _workers_busy += 1
                app_metrics.TTS_SESSION_WORKERS_BUSY.set(_workers_busy)
                app_metrics.TTS_SESSION_QUEUE_DEPTH.set(_queue.qsize())
                session_id = item.session_id
                websocket = item.websocket
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
                    logger.info(
                        "WebSocket disconnected for session %s (worker=%d)",
                        session_id,
                        worker_id,
                    )
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
                        "WebSocket internal error for session %s (worker=%d)",
                        session_id,
                        worker_id,
                        exc_info=True,
                    )
                    err = ErrorMessage(
                        type="error", code=500, message="internal error"
                    )
                    try:
                        await websocket.send_json(err.model_dump())
                    except Exception:
                        pass
                    await websocket.close(code=1011, reason="internal error")
                if not item.future.done():
                    item.future.set_result(None)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Session queue worker %d failed to create session: %s",
                    worker_id,
                    exc,
                    exc_info=True,
                )
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                _workers_busy -= 1
                app_metrics.TTS_SESSION_WORKERS_BUSY.set(_workers_busy)
                _queue.task_done()
                app_metrics.TTS_SESSION_QUEUE_DEPTH.set(_queue.qsize())

    for i in range(worker_count):
        loop.create_task(worker(i + 1))
    _workers_started = True
    logger.info(
        "Streaming queue configured with maxsize=%d, worker_count=%d",
        maxsize,
        worker_count,
    )


async def enqueue_stream_request(
    session_id: str,
    websocket: WebSocket,
) -> None:
    """Enqueue a streaming request and await completion.

    If the queue is not configured, falls back to streaming inline in the
    current task for simplicity. If the queue is full, raises
    SessionQueueFullError.
    """
    from app.container import get_tts_service  # local import to avoid cycles

    if _queue is None:
        # Queue not configured; stream inline.
        logger.debug("Streaming queue not configured; streaming inline.")
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
            return
        except ValueError as exc:
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
        return

    loop = asyncio.get_running_loop()
    fut: asyncio.Future[None] = loop.create_future()
    item = SessionWorkItem(session_id=session_id, websocket=websocket, future=fut)
    try:
        _queue.put_nowait(item)
    except asyncio.QueueFull as exc:
        logger.warning(
            "Session queue full (maxsize=%d) – rejecting new session.",
            _queue.maxsize,
        )
        app_metrics.TTS_SESSION_QUEUE_FULL_TOTAL.inc()
        raise SessionQueueFullError("session queue full") from exc

    app_metrics.TTS_SESSION_QUEUE_DEPTH.set(_queue.qsize())

    return await fut
