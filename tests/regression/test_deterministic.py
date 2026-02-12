from __future__ import annotations

from pathlib import Path

from mcp_qgis.config import load_settings
from mcp_qgis.core.locks import LockManager
from mcp_qgis.core.plan import PlanValidator
from mcp_qgis.core.sessions import SessionManager
from mcp_qgis.core.state import RuntimeState
from mcp_qgis.core.transactions import TransactionManager
from mcp_qgis.tools.dispatcher import ToolDispatcher


def _dispatcher() -> ToolDispatcher:
    root = Path(__file__).resolve().parents[2]
    settings = load_settings()
    return ToolDispatcher(
        settings=settings,
        state=RuntimeState(),
        sessions=SessionManager(),
        locks=LockManager(),
        tx=TransactionManager(),
        plan_validator=PlanValidator(root / "PLAN-IR-SCHEMA.json"),
    )


def test_intent_to_plan_deterministic() -> None:
    d = _dispatcher()
    p1 = d.handle(
        "intent_to_plan",
        {"intent_text": "Раздели участок на 4 + дорога 6м"},
        request_id="reg-1",
        session_id="reg-session",
    )["plan"]
    p2 = d.handle(
        "intent_to_plan",
        {"intent_text": "Раздели участок на 4 + дорога 6м"},
        request_id="reg-2",
        session_id="reg-session",
    )["plan"]
    assert p1 == p2


def test_variant_compare_deterministic() -> None:
    d = _dispatcher()
    payload = {
        "variant_ids": ["v1", "v2"],
        "metrics": {"lot_count": 0.6, "avg_lot_area": 0.4},
        "variant_metrics": {
            "v1": {"lot_count": 10, "avg_lot_area": 300, "regulatory_penalty": 2, "utility_length": 150},
            "v2": {"lot_count": 9, "avg_lot_area": 360, "regulatory_penalty": 0, "utility_length": 120},
        },
    }
    r1 = d.handle("variant_compare", payload, request_id="reg-v1", session_id="reg-session")
    r2 = d.handle("variant_compare", payload, request_id="reg-v2", session_id="reg-session")
    assert r1["winner_variant_id"] == r2["winner_variant_id"]
    assert r1["scores"] == r2["scores"]
