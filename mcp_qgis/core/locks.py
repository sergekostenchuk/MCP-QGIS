from __future__ import annotations

from dataclasses import dataclass

from ..errors import ConflictError


@dataclass
class Lock:
    scope: str
    session_id: str
    lock_type: str


class LockManager:
    def __init__(self) -> None:
        self._locks: dict[str, list[Lock]] = {}

    def acquire(self, scope: str, session_id: str, lock_type: str) -> None:
        current = self._locks.setdefault(scope, [])
        if lock_type == "read_lock":
            if any(l.lock_type == "write_lock" and l.session_id != session_id for l in current):
                raise ConflictError("Write lock is held", {"scope": scope})
            current.append(Lock(scope=scope, session_id=session_id, lock_type=lock_type))
            return

        # write lock
        if any(l.session_id != session_id for l in current):
            raise ConflictError("Lock conflict", {"scope": scope})
        if not any(l.lock_type == "write_lock" for l in current):
            current.append(Lock(scope=scope, session_id=session_id, lock_type=lock_type))

    def release_scope(self, scope: str, session_id: str | None = None) -> None:
        if scope not in self._locks:
            return
        if session_id is None:
            self._locks.pop(scope, None)
            return
        self._locks[scope] = [l for l in self._locks[scope] if l.session_id != session_id]
        if not self._locks[scope]:
            self._locks.pop(scope, None)
