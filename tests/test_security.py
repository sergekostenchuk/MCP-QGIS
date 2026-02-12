from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from mcp_qgis.errors import AuthForbiddenError, PreconditionError
from mcp_qgis.security import AuthorizationManager, ConfirmationManager, AuditLogger


def test_authorization_rejects_unauthorized_role() -> None:
    authz = AuthorizationManager()
    try:
        authz.require("plan_execute", "read_only")
        assert False, "Expected AuthForbiddenError"
    except AuthForbiddenError:
        assert True


def test_confirmation_token_issue_and_consume() -> None:
    mgr = ConfirmationManager(ttl_minutes=1)
    token = mgr.issue(session_id="s1", plan_id="p1")
    mgr.validate_and_consume(token, session_id="s1", plan_id="p1")
    try:
        mgr.validate_and_consume(token, session_id="s1", plan_id="p1")
        assert False, "Expected PreconditionError"
    except PreconditionError:
        assert True


def test_audit_logger_writes_line() -> None:
    with TemporaryDirectory() as td:
        log_path = Path(td) / "audit.log"
        logger = AuditLogger(log_path)
        logger.write({"status": "ok"})
        content = log_path.read_text(encoding="utf-8")
        assert '"status": "ok"' in content
