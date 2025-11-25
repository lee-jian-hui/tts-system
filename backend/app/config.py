from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AppConfig:
    """Application configuration loaded from environment.

    This keeps provider-specific knobs in one place so that provider
    registry and voice metadata can be controlled via .env.
    """
    rate_limit_max_requests_per_window: int = int(
        os.getenv("RATE_LIMIT_MAX_REQUESTS_PER_WINDOW", "50")
    )
    rate_limit_window_seconds: int = int(
        os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    )

    # Bounded session-creation queue configuration.
    session_queue_maxsize: int = int(os.getenv("SESSION_QUEUE_MAXSIZE", "5"))
    session_queue_worker_count: int = int(
        os.getenv("SESSION_QUEUE_WORKER_COUNT", "8")
    )

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
