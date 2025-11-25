from __future__ import annotations

from functools import lru_cache

from app.providers import ProviderRegistry
from app.repositories import InMemoryTTSSessionRepository
from app.services import TTSService, AudioTranscodeService
from app.services.circuit_breaker import CircuitBreakerRegistry
from app.services.rate_limiter import RateLimiter, RateLimitConfig
from app.config import settings

@lru_cache(maxsize=1)
def get_provider_registry() -> ProviderRegistry:
    return ProviderRegistry()


@lru_cache(maxsize=1)
def get_session_repo() -> InMemoryTTSSessionRepository:
    return InMemoryTTSSessionRepository()


@lru_cache(maxsize=1)
def get_transcode_service() -> AudioTranscodeService:
    return AudioTranscodeService()


@lru_cache(maxsize=1)
def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    return CircuitBreakerRegistry()


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    """Return the process-wide IP-based RateLimiter.

    The limits are defined in AppConfig so they can be tuned via
    environment variables.
    """
    config = RateLimitConfig(
        max_requests_per_window=settings.rate_limit_max_requests_per_window,
        window_seconds=settings.rate_limit_window_seconds,
    )
    return RateLimiter(config=config)


@lru_cache(maxsize=1)
def get_tts_service() -> TTSService:
    return TTSService(
        provider_registry=get_provider_registry(),
        session_repo=get_session_repo(),
        transcode_service=get_transcode_service(),
        circuit_breakers=get_circuit_breaker_registry(),
    )
