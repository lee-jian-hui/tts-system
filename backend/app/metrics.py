from __future__ import annotations

from prometheus_client import Counter, Gauge

from app.logging_utils import get_logger


logger = get_logger(__name__)


TTS_SESSIONS_TOTAL = Counter(
    "tts_sessions_total",
    "Total TTS sessions by provider and status.",
    ["provider", "status"],
)

TTS_STREAM_CHUNKS_TOTAL = Counter(
    "tts_stream_chunks_total",
    "Total number of audio chunks streamed.",
    ["provider", "format"],
)

TTS_STREAM_BYTES_TOTAL = Counter(
    "tts_stream_bytes_total",
    "Total number of audio bytes streamed.",
    ["provider", "format"],
)

TTS_ACTIVE_STREAMS = Gauge(
    "tts_active_streams",
    "Current number of active TTS streams.",
    ["provider"],
)

TTS_PROVIDER_FAILURES_TOTAL = Counter(
    "tts_provider_failures_total",
    "Total number of provider failures observed.",
    ["provider"],
)

TTS_BACKEND_DROPPED_FRAMES_TOTAL = Counter(
    "tts_backend_dropped_frames_total",
    "Total number of audio chunks dropped by the backend per provider/format/reason.",
    ["provider", "format", "reason"],
)


def record_session_created(provider_id: str) -> None:
    TTS_SESSIONS_TOTAL.labels(provider=provider_id, status="created").inc()


def record_session_completed(provider_id: str) -> None:
    TTS_SESSIONS_TOTAL.labels(provider=provider_id, status="completed").inc()


def record_session_failed(provider_id: str) -> None:
    TTS_SESSIONS_TOTAL.labels(provider=provider_id, status="failed").inc()


def increment_active_streams(provider_id: str) -> None:
    TTS_ACTIVE_STREAMS.labels(provider=provider_id).inc()


def decrement_active_streams(provider_id: str) -> None:
    TTS_ACTIVE_STREAMS.labels(provider=provider_id).dec()


def record_stream_chunk(provider_id: str, target_format: str, num_bytes: int) -> None:
    TTS_STREAM_CHUNKS_TOTAL.labels(provider=provider_id, format=target_format).inc()
    TTS_STREAM_BYTES_TOTAL.labels(provider=provider_id, format=target_format).inc(
        num_bytes
    )


def record_provider_failure(provider_id: str) -> None:
    TTS_PROVIDER_FAILURES_TOTAL.labels(provider=provider_id).inc()


def record_stream_chunk_dropped(
    provider_id: str,
    target_format: str,
    *,
    reason: str,
) -> None:
    TTS_BACKEND_DROPPED_FRAMES_TOTAL.labels(
        provider=provider_id,
        format=target_format,
        reason=reason,
    ).inc()
