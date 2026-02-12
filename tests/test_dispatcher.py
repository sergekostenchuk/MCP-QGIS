from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from mcp_qgis.config import load_settings
from mcp_qgis.core.state import RuntimeState
from mcp_qgis.core.sessions import SessionManager
from mcp_qgis.core.locks import LockManager
from mcp_qgis.core.transactions import TransactionManager
from mcp_qgis.core.plan import PlanValidator
from mcp_qgis.tools.dispatcher import ToolDispatcher
from mcp_qgis.errors import ValidationError


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


def _valid_plan() -> dict:
    d = _dispatcher()
    out = d.handle(
        "intent_to_plan",
        {"intent_text": "Раздели участок на 4 + дорога 6м"},
        request_id="req-plan-1",
        session_id="sess-1",
    )
    return out["plan"]


def test_project_open_state_layer_catalog() -> None:
    d = _dispatcher()
    with TemporaryDirectory() as td:
        project = Path(td) / "test.qgs"
        project.write_text("<qgis></qgis>", encoding="utf-8")

        opened = d.handle(
            "project_open",
            {"project_path": str(project), "target_crs": "EPSG:32637"},
            request_id="req-open",
            session_id="sess-1",
        )
        assert opened["project_path"] == str(project)

        state = d.handle("project_state", {}, request_id="req-state", session_id="sess-1")
        assert state["crs"] == "EPSG:32637"

        catalog = d.handle("layer_catalog", {}, request_id="req-cat", session_id="sess-1")
        assert len(catalog["layers"]) >= 1


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


def test_plan_execute_dry_run() -> None:
    d = _dispatcher()
    plan = _valid_plan()
    preview = d.handle(
        "plan_preview",
        {"plan": plan, "preview_render": False},
        request_id="req-prev-1",
        session_id="sess-1",
    )
    assert preview["plan_id"] == plan["plan_id"]

    out = d.handle(
        "plan_execute",
        {"plan": plan, "dry_run": True, "adapter_mode": "mock"},
        request_id="req-exec-1",
        session_id="sess-1",
    )
    assert out["status"] == "rolled_back"


def test_plan_execute_dependency_failure() -> None:
    d = _dispatcher()
    plan = _valid_plan()
    plan["steps"][1]["depends_on"] = ["s999"]
    try:
        d.handle(
            "plan_execute",
            {"plan": plan, "dry_run": False, "adapter_mode": "mock"},
            request_id="req-exec-2",
            session_id="sess-1",
        )
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_plan_validate_ruleset_hard_violation() -> None:
    d = _dispatcher()
    plan = _valid_plan()
    plan["constraints"]["lot_metrics"] = [{"lot_id": "L1", "area_m2": 100, "road_access": False}]
    out = d.handle(
        "plan_validate",
        {"plan": plan, "ruleset": "cadastre_default"},
        request_id="req-rule",
        session_id="sess-1",
    )
    assert out["valid"] is False
    assert len(out["errors"]) >= 1


def test_topology_validate_and_variants() -> None:
    d = _dispatcher()
    topo = d.handle(
        "topology_validate",
        {"layer_ids": ["lots"], "summary": {"self_intersections": 0, "overlaps": 0, "gaps": 0}},
        request_id="req-topo",
        session_id="sess-1",
    )
    assert topo["valid"] is True

    v1 = d.handle(
        "variant_create",
        {"name": "variant-1", "base_state": "current"},
        request_id="req-v1",
        session_id="sess-1",
    )
    assert v1["variant_id"] == "variant-1"

    compare = d.handle(
        "variant_compare",
        {
            "variant_ids": ["variant-1", "variant-2"],
            "metrics": {"lot_count": 0.5, "avg_lot_area": 0.5},
        },
        request_id="req-vc",
        session_id="sess-1",
    )
    assert "winner_variant_id" in compare


def test_export_result() -> None:
    d = _dispatcher()
    with TemporaryDirectory() as td:
        path = Path(td) / "out.json"
        out = d.handle(
            "export_result",
            {"targets": ["lots"], "format": "geojson", "path": str(path)},
            request_id="req-exp",
            session_id="sess-1",
        )
        assert path.exists()
        assert out["exports"][0]["target"] == "lots"


def test_git_snapshot() -> None:
    d = _dispatcher()
    with TemporaryDirectory() as td:
        repo = Path(td)
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)
        (repo / "a.txt").write_text("hello", encoding="utf-8")
        out = d.handle(
            "git_snapshot",
            {"message": "snapshot", "repo_path": str(repo)},
            request_id="req-git",
            session_id="sess-1",
        )
        assert out["created"] is True
