from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import subprocess
from uuid import uuid4

from ..config import Settings
from ..core.state import RuntimeState, ProjectState, VariantState
from ..core.sessions import SessionManager
from ..core.locks import LockManager
from ..core.transactions import TransactionManager
from ..core.plan import PlanValidator, build_plan_from_intent
from ..adapters.qgis_adapter import QGISAdapter
from ..validators.ruleset import RulesetLoader
from ..validators.geometry_checks import (
    evaluate_lot_constraints,
    evaluate_topology,
    topology_summary_from_payload,
)
from ..errors import MCPQGISError, ValidationError, NotFoundError, ConflictError


OP_TO_ALGORITHM = {
    "fix": "native:fixgeometries",
    "split": "native:splitwithlines",
    "buffer": "native:buffer",
    "difference": "native:difference",
    "intersection": "native:intersection",
    "snap": "native:snapgeometries",
    "move": "native:translategeometry",
}


class ToolDispatcher:
    def __init__(
        self,
        settings: Settings,
        state: RuntimeState,
        sessions: SessionManager,
        locks: LockManager,
        tx: TransactionManager,
        plan_validator: PlanValidator,
    ) -> None:
        self.settings = settings
        self.state = state
        self.sessions = sessions
        self.locks = locks
        self.tx = tx
        self.plan_validator = plan_validator
        self.adapter = QGISAdapter(mode="mock")
        self.rulesets = RulesetLoader(Path(__file__).resolve().parents[2] / "rulesets")
        self._request_cache: dict[str, dict[str, Any]] = {}

    def handle(self, tool: str, payload: dict[str, Any], request_id: str, session_id: str) -> dict[str, Any]:
        key = request_id
        if key in self._request_cache:
            cached = self._request_cache[key]
            if cached["payload"] != payload or cached["tool"] != tool:
                raise ConflictError("Same request_id with different payload", {"request_id": request_id})
            return cached["result"]

        self.sessions.upsert(session_id)
        handler = getattr(self, f"tool_{tool}", None)
        if handler is None:
            raise NotFoundError("Tool not found", {"tool": tool})
        result = handler(payload=payload, request_id=request_id, session_id=session_id)
        self._request_cache[key] = {"tool": tool, "payload": payload, "result": result}
        return result

    def tool_project_open(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        project_path = payload.get("project_path")
        if not project_path:
            raise ValidationError("project_path is required", {"field": "payload.project_path"})
        read_only = bool(payload.get("read_only", False))
        crs = payload.get("target_crs", "EPSG:32637")

        path = Path(project_path)
        if not path.exists():
            raise NotFoundError("Project file not found", {"project_path": project_path})

        self.state.project = ProjectState(
            project_id=str(uuid4()),
            project_path=str(path),
            crs=crs,
            dirty=False,
            read_only=read_only,
            layer_count=0,
        )
        return {
            "project_id": self.state.project.project_id,
            "project_path": self.state.project.project_path,
            "crs": self.state.project.crs,
            "layer_count": self.state.project.layer_count,
            "read_only": self.state.project.read_only,
        }

    def tool_project_state(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        if not self.state.project:
            raise NotFoundError("No active project", {})
        return {
            "project_id": self.state.project.project_id,
            "project_path": self.state.project.project_path,
            "crs": self.state.project.crs,
            "dirty": self.state.project.dirty,
            "active_transaction": self.state.project.active_transaction,
            "open_variants": list(self.state.variants.keys()),
        }

    def tool_layer_catalog(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        return {
            "layers": [
                {
                    "layer_id": "parcel_src",
                    "name": "parcel_src",
                    "role": "parcel",
                    "geometry_type": "Polygon",
                    "feature_count": 1,
                    "is_valid": True,
                    "fields": [{"name": "parcel_id", "type": "string"}],
                }
            ]
        }

    def tool_intent_to_plan(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        intent_text = payload.get("intent_text")
        if not intent_text:
            raise ValidationError("intent_text is required", {"field": "payload.intent_text"})
        constraints = payload.get("constraints", {})
        plan = build_plan_from_intent(intent_text, constraints)
        return {"plan": plan, "assumptions": [], "missing_inputs": []}

    def tool_plan_preview(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        plan = payload.get("plan")
        if not isinstance(plan, dict):
            raise ValidationError("plan is required", {"field": "payload.plan"})
        est_changes = {
            "new_lots": int(plan.get("context", {}).get("lots_target", 4)),
            "road_area_m2": 1200,
            "geometry_updates": len(plan.get("steps", [])),
        }
        return {
            "plan_id": plan.get("plan_id", "unknown"),
            "estimated_changes": est_changes,
            "warnings": [],
            "render_path": None,
        }

    def tool_plan_validate(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        plan = payload.get("plan")
        ruleset = payload.get("ruleset", "cadastre_default")
        if not isinstance(plan, dict):
            raise ValidationError("plan is required", {"field": "payload.plan"})

        schema_valid, schema_errors = self.plan_validator.validate(plan)
        rule_errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if schema_valid:
            _, rule_errors, warnings = self._validate_plan_rules(plan, ruleset)

        return {
            "plan_id": plan.get("plan_id", "unknown"),
            "valid": schema_valid and len(rule_errors) == 0,
            "errors": schema_errors + rule_errors,
            "warnings": warnings,
        }

    def tool_plan_execute(self, payload: dict[str, Any], session_id: str, **_: Any) -> dict[str, Any]:
        plan = payload.get("plan")
        if not isinstance(plan, dict):
            raise ValidationError("plan is required", {"field": "payload.plan"})

        schema_valid, schema_errors = self.plan_validator.validate(plan)
        if not schema_valid:
            return {
                "plan_id": plan.get("plan_id", "unknown"),
                "transaction_id": None,
                "status": "failed_validation",
                "step_results": [],
                "errors": schema_errors,
                "artifacts": [],
            }

        ruleset_name = payload.get("ruleset", plan.get("ruleset", "cadastre_default"))
        _, rule_errors, _warnings = self._validate_plan_rules(plan, ruleset_name)
        if rule_errors:
            return {
                "plan_id": plan.get("plan_id", "unknown"),
                "transaction_id": None,
                "status": "failed_validation",
                "step_results": [],
                "errors": rule_errors,
                "artifacts": [],
            }

        self.locks.acquire("project:current", session_id, "write_lock")
        tx = self.tx.begin(plan_id=plan["plan_id"], session_id=session_id)
        step_results = []
        completed_steps: set[str] = set()

        try:
            adapter_mode = payload.get("adapter_mode", "mock")
            self.adapter.mode = adapter_mode

            for step in plan.get("steps", []):
                step_id = step["step_id"]
                depends_on = set(step.get("depends_on", []))
                if not depends_on.issubset(completed_steps):
                    missing = sorted(list(depends_on - completed_steps))
                    self.tx.step(tx.transaction_id, step_id, "failed", {"missing_dependencies": missing})
                    raise ValidationError("Step dependency not satisfied", {"step_id": step_id, "missing": missing})

                self.tx.step(tx.transaction_id, step_id, "running")
                op = step.get("op")
                algorithm = OP_TO_ALGORITHM.get(op)
                if algorithm:
                    self.adapter.run_algorithm(algorithm, step.get("params", {}), crs=plan.get("crs", "EPSG:32637"))

                # postchecks (minimal contract)
                for check in step.get("postchecks", []):
                    if check.get("name") == "topology_ok":
                        pass

                self.tx.step(tx.transaction_id, step_id, "done")
                completed_steps.add(step_id)
                step_results.append({"step_id": step_id, "status": "done", "duration_ms": 1})

            if payload.get("dry_run", False):
                self.tx.rollback(tx.transaction_id)
                status = "rolled_back"
            else:
                self.tx.commit(tx.transaction_id)
                status = "committed"
        except MCPQGISError:
            self.tx.rollback(tx.transaction_id)
            raise
        finally:
            self.locks.release_scope("project:current", session_id=session_id)

        if self.state.project:
            self.state.project.active_transaction = tx.transaction_id

        return {
            "plan_id": plan["plan_id"],
            "transaction_id": tx.transaction_id,
            "status": status,
            "step_results": step_results,
            "artifacts": [],
        }

    def tool_topology_validate(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        layer_ids = payload.get("layer_ids")
        if not isinstance(layer_ids, list) or not layer_ids:
            raise ValidationError("layer_ids is required", {"field": "payload.layer_ids"})

        summary = topology_summary_from_payload(payload)
        valid, issues = evaluate_topology(summary)

        return {
            "valid": valid,
            "summary": summary,
            "issues": issues,
        }

    def tool_variant_create(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        name = payload.get("name")
        if not name:
            raise ValidationError("name is required", {"field": "payload.name"})
        variant = VariantState(
            variant_id=name,
            name=name,
            description=payload.get("description", ""),
            created_from=payload.get("base_state", "current"),
        )
        self.state.variants[variant.variant_id] = variant
        return {
            "variant_id": variant.variant_id,
            "created_from": variant.created_from,
            "created_at": "2026-02-12T00:00:00Z",
        }

    def tool_variant_compare(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        variant_ids = payload.get("variant_ids")
        metrics = payload.get("metrics")
        if not isinstance(variant_ids, list) or len(variant_ids) < 2:
            raise ValidationError("variant_ids must contain at least two items", {"field": "payload.variant_ids"})
        if not isinstance(metrics, dict) or not metrics:
            raise ValidationError("metrics is required", {"field": "payload.metrics"})

        scores = []
        base = 1.0 / max(1, len(variant_ids))
        for idx, vid in enumerate(variant_ids):
            score = round(base + (len(variant_ids) - idx) * 0.01, 4)
            scores.append({"variant_id": vid, "score": score})
        winner = sorted(scores, key=lambda x: x["score"], reverse=True)[0]["variant_id"]
        return {"winner_variant_id": winner, "scores": scores, "report_path": None}

    def tool_git_snapshot(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        message = payload.get("message")
        if not message:
            raise ValidationError("message is required", {"field": "payload.message"})

        repo = Path(payload.get("repo_path", Path.cwd()))
        if not (repo / ".git").exists():
            raise NotFoundError("Not a git repository", {"repo_path": str(repo)})

        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True, text=True)
        commit_proc = subprocess.run(
            ["git", "commit", "-m", message], cwd=repo, check=False, capture_output=True, text=True
        )
        stderr = commit_proc.stderr.lower()
        stdout = commit_proc.stdout.lower()
        if commit_proc.returncode != 0 and "nothing to commit" not in stderr and "nothing to commit" not in stdout:
            raise MCPQGISError("git commit failed", {"stderr": commit_proc.stderr.strip()})

        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        )
        return {"commit": rev.stdout.strip(), "branch": branch.stdout.strip(), "created": True}

    def tool_export_result(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        targets = payload.get("targets")
        out_path = payload.get("path")
        out_format = payload.get("format")
        if not isinstance(targets, list) or not targets:
            raise ValidationError("targets is required", {"field": "payload.targets"})
        if not out_path:
            raise ValidationError("path is required", {"field": "payload.path"})
        if not out_format:
            raise ValidationError("format is required", {"field": "payload.format"})

        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "format": out_format,
            "targets": targets,
            "generated": True,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"exports": [{"target": t, "path": str(path), "feature_count": 0} for t in targets]}

    def _validate_plan_rules(self, plan: dict[str, Any], ruleset_name: str) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
        ruleset = self.rulesets.load(ruleset_name)
        lot_metrics = plan.get("constraints", {}).get("lot_metrics", [])
        topology_summary = plan.get("constraints", {}).get("topology_summary", {})

        min_area = 300
        require_road_access = True
        min_frontage = 0.0
        rule_severity: dict[str, str] = {}
        for r in ruleset.get("rules", []):
            rid = str(r.get("rule_id", ""))
            if rid:
                rule_severity[rid] = str(r.get("severity", "hard"))
            if r.get("type") == "area_min":
                min_area = float(r.get("params", {}).get("min_area_m2", min_area))
            if r.get("type") == "road_access":
                require_road_access = bool(r.get("params", {}).get("required", True))
            if r.get("type") == "frontage_min":
                min_frontage = float(r.get("params", {}).get("min_frontage_m", min_frontage))

        hard_ok = True
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if lot_metrics:
            ok, lot_issues = evaluate_lot_constraints(
                lot_metrics,
                min_area_m2=min_area,
                require_road_access=require_road_access,
                min_frontage_m=min_frontage,
            )
            for issue in lot_issues:
                if rule_severity.get(issue.get("rule_id", ""), "hard") == "soft":
                    issue["severity"] = "soft"
                    warnings.append(issue)
                else:
                    errors.append(issue)
            hard_ok = hard_ok and ok

        if topology_summary:
            ok_topo, topo_issues = evaluate_topology(
                {
                    "self_intersections": int(topology_summary.get("self_intersections", 0)),
                    "overlaps": int(topology_summary.get("overlaps", 0)),
                    "gaps": int(topology_summary.get("gaps", 0)),
                }
            )
            for issue in topo_issues:
                if rule_severity.get(issue.get("rule_id", ""), "hard") == "soft":
                    issue["severity"] = "soft"
                    warnings.append(issue)
                else:
                    errors.append(issue)
            hard_ok = hard_ok and ok_topo

        hard_ok = hard_ok and len([i for i in errors if i.get("severity") == "hard"]) == 0
        return hard_ok, errors, warnings
