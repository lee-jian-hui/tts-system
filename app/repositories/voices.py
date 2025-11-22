from __future__ import annotations

from typing import List, Optional

from voice_tts_kr.models import Voice, AudioFormat
from voice_tts_kr.providers import ProviderRegistry


class VoiceRepository:
    """Read-only view over provider voices.

    For MVP this is a thin wrapper over ProviderRegistry; it can
    later be extended to cache or persist voice metadata.
    """

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        self._providers = provider_registry

    async def list_voices(
        self,
        provider: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Voice]:
        provider_voices = await self._providers.list_all_voices()
        items: List[Voice] = []
        for v in provider_voices:
            items.append(
                Voice(
                    id=v.id,
                    name=v.name,
                    language=v.language,
                    provider=self._find_provider_id_for_voice(v.id),
                    sample_rate_hz=v.sample_rate_hz,
                    supported_formats=self._default_formats(),
                )
            )
        if provider:
            items = [i for i in items if i.provider == provider]
        if language:
            items = [i for i in items if i.language == language]
        return items

    def _default_formats(self) -> list[AudioFormat]:
        # For MVP, assume providers can at least output pcm16 and wav
        return ["pcm16", "wav"]  # type: ignore[list-item]

    def _find_provider_id_for_voice(self, voice_id: str) -> str:
        # For minimal implementation there is a single provider,
        # so we can defer a proper mapping until we add more.
        for provider in self._providers.list_providers():
            # Ask provider if it owns the voice; in MVP, assume first match.
            # To avoid an async call, we assume voice_ids are unique and
            # provider implementations know their own IDs.
            # With only MockToneProvider this is trivial.
            return provider.id
        return "unknown"
