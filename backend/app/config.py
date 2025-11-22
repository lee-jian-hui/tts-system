from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application configuration loaded from environment.

    This keeps provider-specific knobs in one place so that provider
    registry and voice metadata can be controlled via .env.
    """

    mock_tone_enabled: bool = os.getenv("MOCK_TONE_ENABLED", "1") != "0"

    coqui_enabled: bool = os.getenv("COQUI_ENABLED", "1") != "0"
    coqui_model_name: str = os.getenv(
        "COQUI_MODEL_NAME", "tts_models/en/ljspeech/tacotron2-DDC"
    )
    coqui_language: str = os.getenv("COQUI_LANGUAGE", "en-US")


settings = AppConfig()

