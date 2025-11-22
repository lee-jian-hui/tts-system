from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Dict, Tuple

from app.logging_utils import get_logger


logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for IP-based rate limiting."""

    max_requests_per_window: int = 10
    window_seconds: int = 60


class RateLimiter:
    """Simple in-memory fixed-window rate limiter keyed by client id.

    For this assignment we key by client IP address for the HTTP API.
    """

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._lock = RLock()
        # key -> (window_start_epoch, count)
        self._buckets: Dict[str, Tuple[float, int]] = {}

    def allow_request(self, key: str) -> bool:
        """Return True if a request from `key` is allowed."""
        now = time.time()
        with self._lock:
            window_start, count = self._buckets.get(key, (now, 0))

            # If the current window has expired, reset the bucket.
            if now - window_start >= self._config.window_seconds:
                window_start = now
                count = 0

            if count >= self._config.max_requests_per_window:
                logger.warning(
                    "Rate limit exceeded for key=%s (count=%d, window_start=%f)",
                    key,
                    count,
                    window_start,
                )
                self._buckets[key] = (window_start, count)
                return False

            # Record the successful request.
            count += 1
            self._buckets[key] = (window_start, count)
            return True

