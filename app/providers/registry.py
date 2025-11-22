from __future__ import annotations

from typing import Dict, Iterable, Optional

from .base import BaseTTSProvider, ProviderVoice
from .mock_tone import MockToneProvider


class ProviderRegistry:
    """Simple in-memory registry for TTS providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, BaseTTSProvider] = {
            MockToneProvider().id: MockToneProvider(),
        }

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

