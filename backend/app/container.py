from __future__ import annotations

from functools import lru_cache

from app.providers import ProviderRegistry
from app.repositories import InMemoryTTSSessionRepository
from app.services import TTSService, AudioTranscodeService
from app.services.circuit_breaker import CircuitBreakerRegistry
from app.services.rate_limiter import RateLimiter


@lru_cache
def get_provider_registry() -> ProviderRegistry:
  return ProviderRegistry()


@lru_cache
def get_session_repo() -> InMemoryTTSSessionRepository:
    return InMemoryTTSSessionRepository()


@lru_cache
def get_transcode_service() -> AudioTranscodeService:
  return AudioTranscodeService()


@lru_cache
def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
  return CircuitBreakerRegistry()


@lru_cache
def get_rate_limiter() -> RateLimiter:
  return RateLimiter()


@lru_cache
def get_tts_service() -> TTSService:
  return TTSService(
    provider_registry=get_provider_registry(),
    session_repo=get_session_repo(),
    transcode_service=get_transcode_service(),
    circuit_breakers=get_circuit_breaker_registry(),
  )
