from __future__ import annotations

from pathlib import Path

from mcp_qgis.config import load_settings
from mcp_qgis.core.state import RuntimeState
from mcp_qgis.core.sessions import SessionManager
from mcp_qgis.core.locks import LockManager
from mcp_qgis.core.transactions import TransactionManager
from mcp_qgis.core.plan import PlanValidator
from mcp_qgis.tools.dispatcher import ToolDispatcher


def _dispatcher() -> ToolDispatcher:
    root = Path(__file__).resolve().parents[1]
    settings = load_settings()
    return ToolDispatcher(
        settings=settings,
        state=RuntimeState(),
        sessions=SessionManager(),
        locks=LockManager(),
        tx=TransactionManager(),
        plan_validator=PlanValidator(root / "PLAN-IR-SCHEMA.json"),
    )


def test_intent_to_plan_then_validate() -> None:
    d = _dispatcher()
    out = d.handle(
        "intent_to_plan",
        {"intent_text": "Раздели участок на 4 + дорога 6м"},
        request_id="req-1",
        session_id="sess-1",
    )
    plan = out["plan"]
    valid = d.handle(
        "plan_validate",
        {"plan": plan, "ruleset": "cadastre_default"},
        request_id="req-2",
        session_id="sess-1",
    )
    assert valid["valid"] is True
