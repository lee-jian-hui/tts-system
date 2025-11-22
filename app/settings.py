from __future__ import annotations

import os
from typing import Callable

from .engines.base import BaseTTSEngine
from .engines.dummy import DummyKoreanEngine


_ENGINE_FACTORIES: dict[str, Callable[[], BaseTTSEngine]] = {
    "dummy": lambda: DummyKoreanEngine(),
}


def get_engine_name() -> str:
    return os.getenv("TTS_ENGINE", "dummy").lower()


def get_engine() -> BaseTTSEngine:
    name = get_engine_name()
    if name not in _ENGINE_FACTORIES:
        raise ValueError(f"Unknown TTS_ENGINE '{name}'")
    return _ENGINE_FACTORIES[name]()


def list_voices() -> list[dict]:
    return get_engine().voices()

