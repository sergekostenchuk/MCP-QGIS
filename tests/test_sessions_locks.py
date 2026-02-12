from __future__ import annotations

from mcp_qgis.core.sessions import SessionManager
from mcp_qgis.core.locks import LockManager
from mcp_qgis.errors import ConflictError


def test_session_upsert_get() -> None:
    sm = SessionManager(timeout_minutes=30)
    sm.upsert("s-1", actor_id="u", role="editor")
    assert sm.get("s-1") is not None


def test_write_lock_conflict() -> None:
    lm = LockManager()
    lm.acquire("project:p1", "s-1", "write_lock")
    try:
        lm.acquire("project:p1", "s-2", "write_lock")
        assert False, "Expected ConflictError"
    except ConflictError:
        assert True
