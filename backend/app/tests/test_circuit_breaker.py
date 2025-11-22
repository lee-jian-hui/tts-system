from __future__ import annotations

import time

import pytest

from app.services.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
)


def test_circuit_breaker_allows_requests_until_threshold() -> None:
    cfg = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=60)
    registry = CircuitBreakerRegistry(config=cfg)
    key = "provider-a"

    # Initially closed, should allow.
    assert registry.allow_request(key) is True

    # Two failures (below threshold) should still allow the next request.
    registry.record_failure(key)
    assert registry.allow_request(key) is True

    registry.record_failure(key)
    assert registry.allow_request(key) is True

    # Third failure reaches threshold; circuit should open and block further calls.
    registry.record_failure(key)
    assert registry.allow_request(key) is False


def test_circuit_breaker_moves_to_half_open_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = CircuitBreakerConfig(failure_threshold=1, reset_timeout_seconds=10)
    registry = CircuitBreakerRegistry(config=cfg)
    key = "provider-b"

    fake_time = [1000.0]

    def fake_time_func() -> float:
        return fake_time[0]

    monkeypatch.setattr("app.services.circuit_breaker.time.time", fake_time_func)

    # Cause a single failure, which opens the circuit immediately (threshold=1).
    registry.record_failure(key)
    assert registry.allow_request(key) is False

    # Advance time beyond reset window; next call should be allowed (half-open).
    fake_time[0] += 11
    assert registry.allow_request(key) is True


def test_circuit_breaker_resets_on_success_after_half_open(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = CircuitBreakerConfig(failure_threshold=1, reset_timeout_seconds=5)
    registry = CircuitBreakerRegistry(config=cfg)
    key = "provider-c"

    fake_time = [2000.0]

    def fake_time_func() -> float:
        return fake_time[0]

    monkeypatch.setattr("app.services.circuit_breaker.time.time", fake_time_func)

    # Open the circuit with one failure.
    registry.record_failure(key)
    assert registry.allow_request(key) is False

    # Move past the timeout so that the next call is half-open and allowed.
    fake_time[0] += 6
    assert registry.allow_request(key) is True

    # A successful call should reset the breaker to closed state.
    registry.record_success(key)
    assert registry.allow_request(key) is True

