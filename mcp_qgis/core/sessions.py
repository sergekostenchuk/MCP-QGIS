from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class Session:
    session_id: str
    actor_id: str
    role: str
    last_seen: datetime


class SessionManager:
    def __init__(self, timeout_minutes: int = 30) -> None:
        self._timeout = timedelta(minutes=timeout_minutes)
        self._sessions: dict[str, Session] = {}

    def upsert(self, session_id: str, actor_id: str = "system", role: str = "editor") -> Session:
        now = datetime.now(tz=timezone.utc)
        s = self._sessions.get(session_id)
        if s:
            s.last_seen = now
            return s
        s = Session(session_id=session_id, actor_id=actor_id, role=role, last_seen=now)
        self._sessions[session_id] = s
        return s

    def get(self, session_id: str) -> Session | None:
        s = self._sessions.get(session_id)
        if not s:
            return None
        if datetime.now(tz=timezone.utc) - s.last_seen > self._timeout:
            self._sessions.pop(session_id, None)
            return None
        return s

    def clear_expired(self) -> int:
        now = datetime.now(tz=timezone.utc)
        expired = [k for k, v in self._sessions.items() if now - v.last_seen > self._timeout]
        for k in expired:
            self._sessions.pop(k, None)
        return len(expired)
