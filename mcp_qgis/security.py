from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import secrets

from .errors import AuthForbiddenError, PreconditionError


TOOL_ACCESS = {
    "project_open": {"editor", "admin"},
    "project_state": {"read_only", "editor", "admin"},
    "layer_catalog": {"read_only", "editor", "admin"},
    "intent_to_plan": {"editor", "admin"},
    "plan_preview": {"read_only", "editor", "admin"},
    "plan_validate": {"read_only", "editor", "admin"},
    "plan_execute": {"editor", "admin"},
    "topology_validate": {"read_only", "editor", "admin"},
    "variant_create": {"editor", "admin"},
    "variant_compare": {"read_only", "editor", "admin"},
    "git_snapshot": {"editor", "admin"},
    "export_result": {"editor", "admin"},
    "execute_code": {"admin"},
}


@dataclass
class ConfirmationToken:
    token: str
    session_id: str
    plan_id: str
    expires_at: datetime
    used: bool = False


class ConfirmationManager:
    def __init__(self, ttl_minutes: int = 10) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._tokens: dict[str, ConfirmationToken] = {}

    def issue(self, session_id: str, plan_id: str) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = ConfirmationToken(
            token=token,
            session_id=session_id,
            plan_id=plan_id,
            expires_at=datetime.now(tz=timezone.utc) + self._ttl,
        )
        return token

    def validate_and_consume(self, token: str, session_id: str, plan_id: str) -> None:
        rec = self._tokens.get(token)
        if not rec:
            raise PreconditionError("Invalid confirmation token", {"token": "unknown"})
        if rec.used:
            raise PreconditionError("Confirmation token already used", {"token": "used"})
        if rec.session_id != session_id or rec.plan_id != plan_id:
            raise PreconditionError("Confirmation token mismatch", {"session_id": session_id, "plan_id": plan_id})
        if datetime.now(tz=timezone.utc) > rec.expires_at:
            raise PreconditionError("Confirmation token expired", {"expired_at": rec.expires_at.isoformat()})
        rec.used = True


class AuthorizationManager:
    def require(self, tool: str, role: str) -> None:
        allowed = TOOL_ACCESS.get(tool, {"admin"})
        if role not in allowed:
            raise AuthForbiddenError("Role is not allowed for tool", {"tool": tool, "role": role, "allowed": sorted(allowed)})


class AuditLogger:
    def __init__(self, log_file: Path) -> None:
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def payload_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
