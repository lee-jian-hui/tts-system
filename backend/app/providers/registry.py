from __future__ import annotations

from typing import Dict, Iterable

from .base import BaseTTSProvider, ProviderVoice
from .mock_tone import MockToneProvider
from . import CoquiTTSProvider
from app.config import settings


class ProviderRegistry:
    """Simple in-memory registry for TTS providers."""

    def __init__(self) -> None:
        providers: Dict[str, BaseTTSProvider] = {}

        if settings.mock_tone_enabled:
            mock = MockToneProvider()
            providers[mock.id] = mock

        if settings.coqui_enabled:
            coqui = CoquiTTSProvider()
            providers[coqui.id] = coqui

        self._providers = providers

    def get(self, provider_id: str) -> BaseTTSProvider:
        try:
            return self._providers[provider_id]
        except KeyError:
            raise ValueError(f"Unknown provider '{provider_id}'")

    def list_providers(self) -> Iterable[BaseTTSProvider]:
        return self._providers.values()

    async def list_all_voices(self) -> list[ProviderVoice]:
        voices: list[ProviderVoice] = []
        for provider in self._providers.values():
            voices.extend(await provider.list_voices())
        return voices
