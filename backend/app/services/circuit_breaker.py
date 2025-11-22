from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Dict

from app.logging_utils import get_logger


logger = get_logger(__name__)


@dataclass
class CircuitBreakerState:
  """In-memory state for a single circuit breaker."""

  failure_count: int = 0
  opened_at: float = 0.0
  state: str = "closed"  # "closed" | "open" | "half_open"


@dataclass
class CircuitBreakerConfig:
  """Configuration for circuit breaker behaviour."""

  failure_threshold: int = 5
  reset_timeout_seconds: int = 30


class CircuitBreakerRegistry:
  """Tracks circuit breaker state per key (e.g., provider id).

  This is intentionally simple and in-memory for the assignment.
  """

  def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
    self._config = config or CircuitBreakerConfig()
    self._lock = RLock()
    self._states: Dict[str, CircuitBreakerState] = {}

  def _get_state(self, key: str) -> CircuitBreakerState:
    with self._lock:
      state = self._states.get(key)
      if state is None:
        state = CircuitBreakerState()
        self._states[key] = state
      return state

  def allow_request(self, key: str) -> bool:
    """Return True if a call should be attempted for this key."""
    state = self._get_state(key)
    now = time.time()

    if state.state == "open":
      if now - state.opened_at >= self._config.reset_timeout_seconds:
        # Move to half-open and allow a trial request.
        logger.warning("Circuit breaker HALF_OPEN for key=%s", key)
        state.state = "half_open"
        return True
      # Still within open window: reject.
      logger.warning("Circuit breaker OPEN – rejecting request for key=%s", key)
      return False

    # closed or half_open: allow request
    return True

  def record_success(self, key: str) -> None:
    """Record a successful call."""
    state = self._get_state(key)
    with self._lock:
      if state.failure_count or state.state != "closed":
        logger.info(
          "Circuit breaker SUCCESS for key=%s (state=%s, failures=%d)",
          key,
          state.state,
          state.failure_count,
        )
      state.failure_count = 0
      state.state = "closed"
      state.opened_at = 0.0

  def record_failure(self, key: str) -> None:
    """Record a failed call and potentially open the circuit."""
    state = self._get_state(key)
    with self._lock:
      state.failure_count += 1
      logger.warning(
        "Circuit breaker failure for key=%s (count=%d)",
        key,
        state.failure_count,
      )
      if state.failure_count >= self._config.failure_threshold:
        state.state = "open"
        state.opened_at = time.time()
        logger.error(
          "Circuit breaker OPEN for key=%s after %d failures",
          key,
          state.failure_count,
        )

