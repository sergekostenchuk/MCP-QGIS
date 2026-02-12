from __future__ import annotations

import json
from pathlib import Path

from mcp_qgis.config import load_settings
from mcp_qgis.core.locks import LockManager
from mcp_qgis.core.plan import PlanValidator
from mcp_qgis.core.sessions import SessionManager
from mcp_qgis.core.state import RuntimeState
from mcp_qgis.core.transactions import TransactionManager
from mcp_qgis.errors import ValidationError
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


def _load_meta(scenario_id: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    meta_path = root / "testdata" / scenario_id / "meta.json"
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _plan_from_text(d: ToolDispatcher, text: str, request_id: str) -> dict:
    out = d.handle(
        "intent_to_plan",
        {"intent_text": text},
        request_id=request_id,
        session_id="e2e-session",
    )
    return out["plan"]


def test_scenario_01_split_road() -> None:
    meta = _load_meta("scenario-01-split-road")
    assert meta["scenario_id"] == "scenario-01-split-road"
    d = _dispatcher()
    plan = _plan_from_text(d, "Раздели участок на 4 + дорога 6м", "e2e-01-plan")
    preview = d.handle("plan_preview", {"plan": plan}, request_id="e2e-01-preview", session_id="e2e-session")
    out = d.handle(
        "plan_execute",
        {
            "plan": plan,
            "dry_run": True,
            "adapter_mode": "mock",
            "require_confirmation_token": preview["confirmation_token"],
        },
        request_id="e2e-01-exec",
        session_id="e2e-session",
    )
    assert out["status"] == "rolled_back"


def test_scenario_02_boundary_shift() -> None:
    meta = _load_meta("scenario-02-boundary-shift")
    assert meta["scenario_id"] == "scenario-02-boundary-shift"
    d = _dispatcher()
    plan = _plan_from_text(d, "Сдвинь границу A/C на 3 м", "e2e-02-plan")
    valid = d.handle("plan_validate", {"plan": plan}, request_id="e2e-02-validate", session_id="e2e-session")
    assert valid["valid"] is True


def test_scenario_03_utilities_constraints() -> None:
    meta = _load_meta("scenario-03-utilities-constraints")
    assert meta["scenario_id"] == "scenario-03-utilities-constraints"
    d = _dispatcher()
    plan = _plan_from_text(d, "Раздели участок на 5 + дорога 7м", "e2e-03-plan")
    plan["constraints"]["lot_metrics"] = [
        {"lot_id": "L1", "area_m2": 450, "road_access": True, "frontage_m": 8},
        {"lot_id": "L2", "area_m2": 500, "road_access": True, "frontage_m": 9},
    ]
    out = d.handle("plan_validate", {"plan": plan}, request_id="e2e-03-validate", session_id="e2e-session")
    assert out["valid"] is True


def test_scenario_04_crs_mismatch() -> None:
    meta = _load_meta("scenario-04-crs-mismatch")
    assert meta["scenario_id"] == "scenario-04-crs-mismatch"
    d = _dispatcher()
    plan = _plan_from_text(d, "Раздели участок на 4 + дорога 6м", "e2e-04-plan")
    plan["crs"] = "EPSG:4326"
    preview = d.handle("plan_preview", {"plan": plan}, request_id="e2e-04-preview", session_id="e2e-session")
    try:
        d.handle(
            "plan_execute",
            {
                "plan": plan,
                "dry_run": True,
                "adapter_mode": "mock",
                "require_confirmation_token": preview["confirmation_token"],
            },
            request_id="e2e-04-exec",
            session_id="e2e-session",
        )
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_scenario_05_recovery_rollback() -> None:
    meta = _load_meta("scenario-05-recovery-rollback")
    assert meta["scenario_id"] == "scenario-05-recovery-rollback"
    d = _dispatcher()
    plan = _plan_from_text(d, "Раздели участок на 4 + дорога 6м", "e2e-05-plan")
    plan["steps"][1]["depends_on"] = ["s999"]
    preview = d.handle("plan_preview", {"plan": plan}, request_id="e2e-05-preview", session_id="e2e-session")
    try:
        d.handle(
            "plan_execute",
            {
                "plan": plan,
                "dry_run": False,
                "adapter_mode": "mock",
                "require_confirmation_token": preview["confirmation_token"],
            },
            request_id="e2e-05-exec",
            session_id="e2e-session",
        )
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True
