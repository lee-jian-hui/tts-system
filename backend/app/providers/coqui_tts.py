from __future__ import annotations

from typing import AsyncIterator

from .base import AudioChunk, BaseTTSProvider, ProviderVoice
from TTS.api import TTS as CoquiTTS  # type: ignore[import]

class CoquiTTSProvider(BaseTTSProvider):
    """Offline TTS provider backed by Coqui TTS.

    This is a simple, blocking implementation intended for local use.
    It synthesizes the full utterance to a WAV file and then streams
    the PCM16 frames as AudioChunk instances.
    """

    id: str = "coqui_tts"

    def __init__(
        self,
        model_name: str | None = None,
        language: str = "en-US",
        chunk_size_frames: int = 1600,
    ) -> None:
        # A commonly used English Coqui model; users can override this.
        self._model_name = model_name or "tts_models/en/ljspeech/tacotron2-DDC"
        self._language = language
        self._tts = CoquiTTS(model_name=self._model_name, progress_bar=False, gpu=False)

        # Coqui exposes the output sample rate via synthesizer.
        self._sample_rate_hz = int(getattr(self._tts.synthesizer, "output_sample_rate", 22050))
        self._chunk_size_frames = chunk_size_frames

        self._voices: list[ProviderVoice] = [
            ProviderVoice(
                id="coqui-en-1",
                name=f"Coqui {self._model_name}",
                language=self._language,
                sample_rate_hz=self._sample_rate_hz,
                base_format="pcm16",
            )
        ]

    async def list_voices(self) -> list[ProviderVoice]:
        return self._voices

    async def stream_synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        language: str | None = None,
    ) -> AsyncIterator[AudioChunk]:
        import tempfile
        import wave

        if not text:
            raise ValueError("text must not be empty")

        # For MVP we ignore voice_id and use the default model voice.
        # Language is also taken from the configured provider language.
        lang = language or self._language

        # Synthesize full utterance to a temporary WAV file.
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            self._tts.tts_to_file(
                text=text,
                file_path=tmp.name,
                # Some models use multi-speaker / multi-language; for the
                # simplest setup we rely on defaults.
                language=lang if "multi" in self._model_name else None,
            )
            tmp.flush()
            tmp.seek(0)

            with wave.open(tmp, "rb") as wf:
                sample_rate = wf.getframerate()
                num_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()

                if sample_width != 2:
                    raise ValueError("Expected 16-bit PCM data from Coqui TTS")

                # Read the WAV file in fixed-size frame chunks and yield
                # raw PCM16 bytes as AudioChunk objects.
                while True:
                    frames = wf.readframes(self._chunk_size_frames)
                    if not frames:
                        break
                    yield AudioChunk(
                        data=frames,
                        sample_rate_hz=sample_rate,
                        num_channels=num_channels,
                        format="pcm16",
                    )
