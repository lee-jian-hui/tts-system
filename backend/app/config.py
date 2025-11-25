from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application configuration loaded from environment.

    This keeps provider-specific knobs in one place so that provider
    registry and voice metadata can be controlled via .env.
    """
    # TODO:
    RATE_LIMIT_MAX_REQUESTS_PER_WINDOW = 10
    RATE_LIMIT_WINDOW_SECONDS = 60

    mock_tone_enabled: bool = os.getenv("MOCK_TONE_ENABLED", "1") != "0"

    coqui_enabled: bool = os.getenv("COQUI_ENABLED", "1") != "0"
    # Optional explicit model path; if set, the Coqui provider will load the
    # model from this path instead of downloading by name.
    coqui_model_path: str | None = os.getenv("COQUI_MODEL_PATH") or None
    coqui_model_name: str = os.getenv(
        "COQUI_MODEL_NAME", "tts_models/en/ljspeech/tacotron2-DDC"
    )
    coqui_language: str = os.getenv("COQUI_LANGUAGE", "en-US")


settings = AppConfig()
