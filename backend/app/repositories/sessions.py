from __future__ import annotations

from threading import RLock
from typing import Dict, Optional, Protocol

from ..models import TTSSession, SessionStatus


class TTSSessionRepository(Protocol):
    """Persistence interface for TTS sessions."""

    def get(self, session_id: str) -> Optional[TTSSession]:
        ...

    def save(self, session: TTSSession) -> None:
        ...

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        ...


class InMemoryTTSSessionRepository(TTSSessionRepository):
    """Simple in-memory session store for development and tests."""

    def __init__(self) -> None:
        self._items: Dict[str, TTSSession] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> Optional[TTSSession]:
        with self._lock:
            return self._items.get(session_id)

    def save(self, session: TTSSession) -> None:
        with self._lock:
            self._items[session.id] = session

    def update_status(self, session_id: str, status: SessionStatus) -> None:
        with self._lock:
            session = self._items.get(session_id)
            if not session:
                return
            session.status = status

