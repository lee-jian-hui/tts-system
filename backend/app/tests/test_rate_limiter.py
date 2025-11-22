from __future__ import annotations

import pytest

from app.services.rate_limiter import RateLimitConfig, RateLimiter


def test_rate_limiter_allows_requests_within_window() -> None:
    cfg = RateLimitConfig(max_requests_per_window=2, window_seconds=60)
    limiter = RateLimiter(config=cfg)
    key = "1.2.3.4"

    assert limiter.allow_request(key) is True
    assert limiter.allow_request(key) is True
    # Third request in the same window should be rejected.
    assert limiter.allow_request(key) is False


def test_rate_limiter_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = RateLimitConfig(max_requests_per_window=1, window_seconds=10)
    limiter = RateLimiter(config=cfg)
    key = "5.6.7.8"

    fake_time = [1000.0]

    def fake_time_func() -> float:
        return fake_time[0]

    monkeypatch.setattr("app.services.rate_limiter.time.time", fake_time_func)

    # First request in window is allowed.
    assert limiter.allow_request(key) is True
    # Immediately calling again should be blocked.
    assert limiter.allow_request(key) is False

    # Advance beyond the window; bucket should reset.
    fake_time[0] += 11
    assert limiter.allow_request(key) is True

