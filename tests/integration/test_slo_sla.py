from __future__ import annotations

from math import ceil
from pathlib import Path
import time

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


def _percentile(values: list[float], p: float) -> float:
    data = sorted(values)
    idx = max(0, ceil(len(data) * p) - 1)
    return data[idx]


def test_slo_preview_execute_and_sla_reliability() -> None:
    d = _dispatcher()
    plan = d.handle(
        "intent_to_plan",
        {"intent_text": "Раздели участок на 4 + дорога 6м"},
        request_id="slo-plan",
        session_id="slo-session",
    )["plan"]

    preview_times: list[float] = []
    execute_times: list[float] = []
    total_exec = 20
    success_exec = 0

    for i in range(total_exec):
        t0 = time.perf_counter()
        preview = d.handle(
            "plan_preview",
            {"plan": plan},
            request_id=f"slo-preview-{i}",
            session_id="slo-session",
        )
        preview_times.append(time.perf_counter() - t0)

        t1 = time.perf_counter()
        out = d.handle(
            "plan_execute",
            {
                "plan": plan,
                "dry_run": True,
                "adapter_mode": "mock",
                "require_confirmation_token": preview["confirmation_token"],
            },
            request_id=f"slo-exec-{i}",
            session_id="slo-session",
        )
        execute_times.append(time.perf_counter() - t1)
        if out["status"] == "rolled_back":
            success_exec += 1

    p95_preview = _percentile(preview_times, 0.95)
    p95_execute = _percentile(execute_times, 0.95)
    reliability = success_exec / total_exec

    assert p95_preview <= 5.0
    assert p95_execute <= 120.0
    assert reliability >= 0.99


def test_rollback_quality_target() -> None:
    d = _dispatcher()
    total = 20
    rollback_ok = 0

    for i in range(total):
        plan = d.handle(
            "intent_to_plan",
            {"intent_text": "Раздели участок на 4 + дорога 6м"},
            request_id=f"rb-plan-{i}",
            session_id="rb-session",
        )["plan"]
        plan["steps"][1]["depends_on"] = ["s999"]
        preview = d.handle(
            "plan_preview",
            {"plan": plan},
            request_id=f"rb-preview-{i}",
            session_id="rb-session",
        )

        try:
            d.handle(
                "plan_execute",
                {
                    "plan": plan,
                    "dry_run": False,
                    "adapter_mode": "mock",
                    "require_confirmation_token": preview["confirmation_token"],
                },
                request_id=f"rb-exec-{i}",
                session_id="rb-session",
            )
        except ValidationError:
            pass

        if any(tx.status == "rolled_back" for tx in d.tx._tx.values()):
            rollback_ok += 1

    assert rollback_ok / total >= 0.995
