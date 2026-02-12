from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from typing import Any

from mcp_qgis.config import load_settings
from mcp_qgis.core.state import RuntimeState, ProjectState
from mcp_qgis.core.sessions import SessionManager
from mcp_qgis.core.locks import LockManager
from mcp_qgis.core.transactions import TransactionManager
from mcp_qgis.core.plan import PlanValidator
from mcp_qgis.tools.dispatcher import ToolDispatcher
from mcp_qgis.errors import ValidationError, PreconditionError


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


def _confirmation_token(d: ToolDispatcher, plan: dict, request_id: str = "req-prev") -> str:
    preview = d.handle(
        "plan_preview",
        {"plan": plan, "preview_render": False},
        request_id=request_id,
        session_id="sess-1",
    )
    token = preview.get("confirmation_token")
    assert isinstance(token, str) and token
    return token


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


def test_project_open_state_layer_catalog_via_bridge(monkeypatch: Any) -> None:
    d = _dispatcher()

    def _open_project(project_path: str, read_only: bool = False) -> dict[str, Any]:
        assert project_path == "/virtual/demo.qgz"
        return {"status": "ok", "project_path": project_path, "crs": "EPSG:32637", "dirty": False, "layer_count": 2}

    def _project_state() -> dict[str, Any]:
        return {"status": "ok", "project_path": "/virtual/demo.qgz", "crs": "EPSG:32637", "dirty": True, "layer_count": 2}

    def _layer_catalog() -> dict[str, Any]:
        return {
            "status": "ok",
            "layers": [
                {
                    "layer_id": "L1",
                    "name": "parcel_src",
                    "geometry_type": "Polygon",
                    "feature_count": 1,
                    "is_valid": True,
                    "fields": [],
                },
                {
                    "layer_id": "L2",
                    "name": "road_axis",
                    "geometry_type": "LineString",
                    "feature_count": 1,
                    "is_valid": True,
                    "fields": [],
                },
            ],
        }

    monkeypatch.setattr(d.adapter, "open_project", _open_project)
    monkeypatch.setattr(d.adapter, "project_state", _project_state)
    monkeypatch.setattr(d.adapter, "layer_catalog", _layer_catalog)

    opened = d.handle(
        "project_open",
        {
            "project_path": "/virtual/demo.qgz",
            "adapter_mode": "mode_a_plugin_bridge",
            "bridge": {"host": "127.0.0.1", "port": 9876},
        },
        request_id="req-open-live",
        session_id="sess-live",
    )
    assert opened["adapter_mode"] == "mode_a_plugin_bridge"
    assert opened["layer_count"] == 2

    state = d.handle("project_state", {}, request_id="req-state-live", session_id="sess-live")
    assert state["dirty"] is True
    assert state["layer_count"] == 2

    catalog = d.handle("layer_catalog", {}, request_id="req-cat-live", session_id="sess-live")
    assert len(catalog["layers"]) == 2
    assert d.state.project is not None
    assert d.state.project.layer_aliases.get("parcel_src") == "L1"
    assert d.state.project.layer_aliases.get("road_axis") == "L2"


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


def test_plan_execute_uses_mapped_processing_params(monkeypatch: Any) -> None:
    d = _dispatcher()
    d.state.project = ProjectState(
        project_id="p1",
        project_path="/tmp/demo.qgs",
        crs="EPSG:32637",
        adapter_mode="mock",
        layer_aliases={"parcel_src": "LAYER_PARCEL", "road_axis": "LAYER_ROAD"},
    )
    plan = _valid_plan()
    captured: list[dict[str, Any]] = []

    def _run_algorithm(algorithm: str, parameters: dict[str, Any], crs: str = "EPSG:32637") -> dict[str, Any]:
        captured.append({"algorithm": algorithm, "parameters": parameters, "crs": crs})
        return {"status": "ok", "result": {"OUTPUT": parameters.get("OUTPUT", "memory:out")}}

    monkeypatch.setattr(d.adapter, "run_algorithm", _run_algorithm)

    out = d.handle(
        "plan_execute",
        {"plan": plan, "dry_run": True, "adapter_mode": "mock"},
        request_id="req-exec-map",
        session_id="sess-1",
    )

    assert out["status"] == "rolled_back"
    assert captured[0]["parameters"]["INPUT"] == "LAYER_PARCEL"
    assert captured[1]["parameters"]["LINES"] == "LAYER_ROAD"
    assert captured[2]["parameters"]["DISTANCE"] == 3.0


def test_plan_execute_dependency_failure() -> None:
    d = _dispatcher()
    plan = _valid_plan()
    plan["steps"][1]["depends_on"] = ["s999"]
    token = _confirmation_token(d, plan, request_id="req-prev-2")
    try:
        d.handle(
            "plan_execute",
            {
                "plan": plan,
                "dry_run": False,
                "adapter_mode": "mock",
                "require_confirmation_token": token,
            },
            request_id="req-exec-2",
            session_id="sess-1",
        )
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_plan_execute_requires_confirmation_token_for_high_risk() -> None:
    d = _dispatcher()
    plan = _valid_plan()
    try:
        d.handle(
            "plan_execute",
            {"plan": plan, "dry_run": False, "adapter_mode": "mock"},
            request_id="req-exec-confirm",
            session_id="sess-1",
        )
        assert False, "Expected PreconditionError"
    except PreconditionError:
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


def test_execute_code_default_deny() -> None:
    d = _dispatcher()
    try:
        d.handle(
            "execute_code",
            {"code": "result = 1 + 1", "_role": "admin"},
            request_id="req-code",
            session_id="sess-1",
        )
        assert False, "Expected PreconditionError"
    except PreconditionError:
        assert True


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
