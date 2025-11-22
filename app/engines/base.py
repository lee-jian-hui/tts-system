from typing import Protocol, Tuple


class BaseTTSEngine(Protocol):
    def voices(self) -> list[dict]:
        """Return a list of available voices with metadata.

        Example item: {"id": "ko-neutral", "name": "Korean Neutral", "lang": "ko-KR"}
        """
        ...

    def synthesize(
        self,
        *,
        text: str,
        voice: str | None,
        rate: float,
        pitch: float,
        sample_rate: int,
        audio_format: str,
    ) -> Tuple[bytes, int, str]:
        """Synthesize text to audio.

        Returns (audio_bytes, sample_rate, mime_type).
        """
        ...

