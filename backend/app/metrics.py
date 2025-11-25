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

TTS_RATE_LIMIT_HITS_TOTAL = Counter(
    "tts_rate_limit_hits_total",
    "Total number of HTTP requests rejected by the rate limiter.",
    ["scope"],
)

TTS_RATE_LIMIT_MAX_BUCKET_USAGE = Gauge(
    "tts_rate_limit_max_bucket_usage",
    "Maximum per-key request count as a fraction of the configured limit "
    "across all keys currently tracked by the rate limiter.",
    ["scope"],
)

TTS_RATE_LIMIT_WINDOW_REMAINING_SECONDS = Gauge(
    "tts_rate_limit_window_remaining_seconds",
    "Estimated number of seconds until the rate-limit window resets "
    "for the most recently seen key in this scope.",
    ["scope"],
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


def record_rate_limit_hit(scope: str) -> None:
    """Record that a request was rejected by the rate limiter."""
    TTS_RATE_LIMIT_HITS_TOTAL.labels(scope=scope).inc()


def record_rate_limit_max_bucket_usage(scope: str, usage_fraction: float) -> None:
    """Record the current maximum bucket usage across all keys for a limiter.

    `usage_fraction` should be in the range [0, 1], representing the ratio of
    the most heavily used key's count to the configured max_requests_per_window.
    """
    TTS_RATE_LIMIT_MAX_BUCKET_USAGE.labels(scope=scope).set(usage_fraction)


def record_rate_limit_window_remaining(scope: str, remaining_seconds: float) -> None:
    """Record approximate remaining time until the rate-limit window resets."""
    TTS_RATE_LIMIT_WINDOW_REMAINING_SECONDS.labels(scope=scope).set(
        max(0.0, remaining_seconds)
    )
