from __future__ import annotations

from datetime import datetime, timezone
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
from ..core.plan import PlanValidator
from ..planner import IntentPlanner
from ..plan_mapper import PlanStepMapper
from ..adapters.qgis_adapter import QGISAdapter
from ..validators.ruleset import RulesetLoader
from ..validators.geometry_checks import (
    evaluate_lot_constraints,
    evaluate_topology,
    topology_summary_from_payload,
)
from ..security import AuthorizationManager, ConfirmationManager, AuditLogger
from ..artifacts import ArtifactManager
from ..variants import compare_variants, write_variant_report
from ..errors import MCPQGISError, ValidationError, NotFoundError, ConflictError, PreconditionError


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

        self.adapter = QGISAdapter(mode="mock", allowlist=self._load_allowlist())
        self.rulesets = RulesetLoader(Path(__file__).resolve().parents[2] / "rulesets")
        self.intent_planner = IntentPlanner()
        self.step_mapper = PlanStepMapper()
        self.authz = AuthorizationManager()
        self.confirm = ConfirmationManager(ttl_minutes=10)
        self.audit = AuditLogger(settings.data_root / "logs" / "audit.log")
        self.artifacts = ArtifactManager(settings.data_root)

        self._request_cache: dict[str, dict[str, Any]] = {}

    def _load_allowlist(self) -> set[str] | None:
        if not self.settings.allowed_algorithms_file:
            return None
        path = self.settings.allowed_algorithms_file
        if not path.exists():
            raise PreconditionError("Allowed algorithms file does not exist", {"path": str(path)})
        values = {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        return values or None

    def _configure_adapter(self, payload: dict[str, Any], default_mode: str = "mock") -> str:
        adapter_mode = str(payload.get("adapter_mode", default_mode))
        self.adapter.mode = adapter_mode
        self.adapter.timeout_sec = int(payload.get("timeout_sec", self.adapter.timeout_sec))
        self.adapter.max_attempts = int(payload.get("max_attempts", self.adapter.max_attempts))
        self.adapter.retry_backoff_sec = float(payload.get("retry_backoff_sec", self.adapter.retry_backoff_sec))
        if adapter_mode == "mode_a_plugin_bridge":
            bridge = payload.get("bridge", {})
            self.adapter.bridge_host = str(bridge.get("host", "127.0.0.1"))
            self.adapter.bridge_port = int(bridge.get("port", 9876))
        return adapter_mode

    @staticmethod
    def _build_layer_aliases(layers: list[dict[str, Any]]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for layer in layers:
            layer_id = str(layer.get("layer_id", ""))
            name = str(layer.get("name", ""))
            if not layer_id:
                continue

            normalized_name = name.strip().lower()
            if normalized_name:
                aliases[normalized_name] = layer_id

            role = str(layer.get("role", "")).strip().lower()
            if role:
                aliases[role] = layer_id

            if "parcel" in normalized_name or "участ" in normalized_name:
                aliases.setdefault("parcel_src", layer_id)
            if "lot" in normalized_name or "лот" in normalized_name:
                aliases.setdefault("lots", layer_id)
            if "road" in normalized_name or "дорог" in normalized_name:
                aliases.setdefault("road_axis", layer_id)
                aliases.setdefault("road_corridor", layer_id)
            if "util" in normalized_name or "коммун" in normalized_name or "сеть" in normalized_name:
                aliases.setdefault("utilities", layer_id)
        return aliases

    def _resolve_layer_ref(self, ref: str, outputs: dict[str, str]) -> str:
        if ref in outputs:
            return outputs[ref]
        if self.state.project:
            aliases = self.state.project.layer_aliases
            if ref in aliases:
                return aliases[ref]
            lower = ref.lower()
            if lower in aliases:
                return aliases[lower]
        return ref

    @staticmethod
    def _extract_output_reference(step_id: str, mapped_params: dict[str, Any], adapter_result: dict[str, Any] | None) -> str | None:
        fallback = mapped_params.get("OUTPUT")
        if not adapter_result:
            return str(fallback) if fallback else None

        result_block = adapter_result.get("result")
        candidates: list[dict[str, Any]] = []
        if isinstance(result_block, dict):
            candidates.append(result_block)
            nested = result_block.get("result")
            if isinstance(nested, dict):
                candidates.append(nested)
            nested_results = result_block.get("results")
            if isinstance(nested_results, dict):
                candidates.append(nested_results)

        for candidate in candidates:
            for key in ("OUTPUT", "output", "OUTPUT_LAYER", "sink"):
                if key in candidate and candidate[key]:
                    return str(candidate[key])

        if fallback:
            return str(fallback)
        return f"memory:{step_id}"

    def _audit(
        self,
        *,
        request_id: str,
        session_id: str,
        actor_id: str,
        role: str,
        tool: str,
        payload: dict[str, Any],
        status: str,
        error: MCPQGISError | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "request_id": request_id,
            "session_id": session_id,
            "actor_id": actor_id,
            "role": role,
            "tool": tool,
            "payload_hash": self.audit.payload_hash(payload),
            "status": status,
        }
        if error:
            record["error_code"] = error.code
            record["error_message"] = error.message
        self.audit.write(record)

    def handle(self, tool: str, payload: dict[str, Any], request_id: str, session_id: str) -> dict[str, Any]:
        key = request_id
        if key in self._request_cache:
            cached = self._request_cache[key]
            if cached["payload"] != payload or cached["tool"] != tool:
                raise ConflictError("Same request_id with different payload", {"request_id": request_id})
            return cached["result"]

        actor_id = str(payload.get("_actor_id", "system"))
        role = str(payload.get("_role", "editor"))
        self.sessions.upsert(session_id, actor_id=actor_id, role=role)
        self.authz.require(tool, role)

        handler = getattr(self, f"tool_{tool}", None)
        if handler is None:
            raise NotFoundError("Tool not found", {"tool": tool})

        try:
            result = handler(payload=payload, request_id=request_id, session_id=session_id, role=role)
            self._request_cache[key] = {"tool": tool, "payload": payload, "result": result}
            self._audit(
                request_id=request_id,
                session_id=session_id,
                actor_id=actor_id,
                role=role,
                tool=tool,
                payload=payload,
                status="ok",
            )
            return result
        except MCPQGISError as err:
            self._audit(
                request_id=request_id,
                session_id=session_id,
                actor_id=actor_id,
                role=role,
                tool=tool,
                payload=payload,
                status="error",
                error=err,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            wrapped = MCPQGISError("Unhandled dispatcher error", {"error": str(exc)})
            self._audit(
                request_id=request_id,
                session_id=session_id,
                actor_id=actor_id,
                role=role,
                tool=tool,
                payload=payload,
                status="error",
                error=wrapped,
            )
            raise

    def tool_project_open(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        project_path = payload.get("project_path")
        if not project_path:
            raise ValidationError("project_path is required", {"field": "payload.project_path"})
        read_only = bool(payload.get("read_only", False))
        crs = payload.get("target_crs", "EPSG:32637")
        adapter_mode = self._configure_adapter(payload, default_mode="mock")

        layer_count = 0
        bridge_host = None
        bridge_port = None
        layer_aliases: dict[str, str] = {}

        if adapter_mode == "mode_a_plugin_bridge":
            opened = self.adapter.open_project(str(project_path), read_only=read_only)
            crs = str(opened.get("crs", crs))
            layer_count = int(opened.get("layer_count", 0))
            bridge_host = self.adapter.bridge_host
            bridge_port = self.adapter.bridge_port
            catalog = self.adapter.layer_catalog()
            layers = catalog.get("layers", [])
            if isinstance(layers, list):
                layer_count = max(layer_count, len(layers))
                layer_aliases = self._build_layer_aliases([l for l in layers if isinstance(l, dict)])
        else:
            path = Path(project_path)
            if not path.exists():
                raise NotFoundError("Project file not found", {"project_path": project_path})

        self.state.project = ProjectState(
            project_id=str(uuid4()),
            project_path=str(project_path),
            crs=str(crs),
            dirty=False,
            read_only=read_only,
            layer_count=layer_count,
            active_transaction=None,
            adapter_mode=adapter_mode,
            bridge_host=bridge_host,
            bridge_port=bridge_port,
            layer_aliases=layer_aliases,
        )
        return {
            "project_id": self.state.project.project_id,
            "project_path": self.state.project.project_path,
            "crs": self.state.project.crs,
            "layer_count": self.state.project.layer_count,
            "read_only": self.state.project.read_only,
            "adapter_mode": self.state.project.adapter_mode,
            "bridge_host": self.state.project.bridge_host,
            "bridge_port": self.state.project.bridge_port,
        }

    def tool_project_state(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        if not self.state.project:
            raise NotFoundError("No active project", {})
        if self.state.project.adapter_mode == "mode_a_plugin_bridge":
            self._configure_adapter(
                {
                    "adapter_mode": "mode_a_plugin_bridge",
                    "bridge": {
                        "host": self.state.project.bridge_host or "127.0.0.1",
                        "port": self.state.project.bridge_port or 9876,
                    },
                },
                default_mode="mode_a_plugin_bridge",
            )
            live_state = self.adapter.project_state()
            self.state.project.crs = str(live_state.get("crs", self.state.project.crs))
            self.state.project.dirty = bool(live_state.get("dirty", self.state.project.dirty))
            self.state.project.layer_count = int(live_state.get("layer_count", self.state.project.layer_count))
            live_path = live_state.get("project_path")
            if live_path:
                self.state.project.project_path = str(live_path)
        return {
            "project_id": self.state.project.project_id,
            "project_path": self.state.project.project_path,
            "crs": self.state.project.crs,
            "dirty": self.state.project.dirty,
            "active_transaction": self.state.project.active_transaction,
            "open_variants": list(self.state.variants.keys()),
            "layer_count": self.state.project.layer_count,
            "adapter_mode": self.state.project.adapter_mode,
        }

    def tool_layer_catalog(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        if self.state.project and self.state.project.adapter_mode == "mode_a_plugin_bridge":
            self._configure_adapter(
                {
                    "adapter_mode": "mode_a_plugin_bridge",
                    "bridge": {
                        "host": self.state.project.bridge_host or "127.0.0.1",
                        "port": self.state.project.bridge_port or 9876,
                    },
                },
                default_mode="mode_a_plugin_bridge",
            )
            catalog = self.adapter.layer_catalog()
            layers = catalog.get("layers", [])
            if isinstance(layers, list):
                typed_layers = [l for l in layers if isinstance(l, dict)]
                self.state.project.layer_count = len(typed_layers)
                self.state.project.layer_aliases = self._build_layer_aliases(typed_layers)
                return {"layers": typed_layers}

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

        planned = self.intent_planner.build_plan(intent_text, constraints)
        return {
            "plan": planned["plan"],
            "assumptions": planned["assumptions"],
            "missing_inputs": planned["missing_inputs"],
            "intent_type": planned["intent_type"],
        }

    def _is_high_risk_plan(self, plan: dict[str, Any]) -> bool:
        if not plan:
            return False
        high_risk_ops = {"difference", "move", "commit", "rollback"}
        return any(step.get("op") in high_risk_ops for step in plan.get("steps", []))

    def tool_plan_preview(self, payload: dict[str, Any], session_id: str, **_: Any) -> dict[str, Any]:
        plan = payload.get("plan")
        if not isinstance(plan, dict):
            raise ValidationError("plan is required", {"field": "payload.plan"})

        est_changes = {
            "new_lots": int(plan.get("context", {}).get("lots_target", 0)),
            "road_area_m2": float(plan.get("context", {}).get("road_width_m", 0)) * 200.0,
            "geometry_updates": len(plan.get("steps", [])),
        }
        high_risk = self._is_high_risk_plan(plan)
        token = None
        if high_risk:
            token = self.confirm.issue(session_id=session_id, plan_id=plan.get("plan_id", "unknown"))

        return {
            "plan_id": plan.get("plan_id", "unknown"),
            "estimated_changes": est_changes,
            "warnings": [],
            "risk_level": "high" if high_risk else "low",
            "confirmation_required": high_risk,
            "confirmation_token": token,
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
            "valid": schema_valid and len([e for e in rule_errors if e.get("severity") == "hard"]) == 0,
            "errors": schema_errors + rule_errors,
            "warnings": warnings,
        }

    def tool_plan_execute(self, payload: dict[str, Any], session_id: str, role: str, **_: Any) -> dict[str, Any]:
        plan = payload.get("plan")
        if not isinstance(plan, dict):
            raise ValidationError("plan is required", {"field": "payload.plan"})

        if self._is_high_risk_plan(plan) and not payload.get("dry_run", False):
            token = payload.get("require_confirmation_token")
            if not token:
                raise PreconditionError("High-risk plan requires confirmation token", {"plan_id": plan.get("plan_id")})
            self.confirm.validate_and_consume(token, session_id=session_id, plan_id=plan.get("plan_id", "unknown"))

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
        hard_errors = [e for e in rule_errors if e.get("severity") == "hard"]
        if hard_errors:
            return {
                "plan_id": plan.get("plan_id", "unknown"),
                "transaction_id": None,
                "status": "failed_validation",
                "step_results": [],
                "errors": hard_errors,
                "artifacts": [],
            }

        self.locks.acquire("project:current", session_id, "write_lock")
        tx = self.tx.begin(plan_id=plan["plan_id"], session_id=session_id)
        step_results = []
        completed_steps: set[str] = set()
        intermediate_outputs: dict[str, str] = {}

        try:
            adapter_mode = self._configure_adapter(payload, default_mode="mock")

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
                algorithm_result: dict[str, Any] | None = None
                if algorithm:
                    mapped_params = self.step_mapper.map_step(
                        step,
                        resolve_layer=lambda ref: self._resolve_layer_ref(ref, intermediate_outputs),
                        default_output=f"memory:{step_id}",
                    )
                    algorithm_result = self.adapter.run_algorithm(
                        algorithm,
                        mapped_params,
                        crs=plan.get("crs", "EPSG:32637"),
                    )
                    output_ref = self._extract_output_reference(step_id, mapped_params, algorithm_result)
                    if output_ref:
                        intermediate_outputs[step_id] = output_ref

                # postchecks placeholders
                for check in step.get("postchecks", []):
                    if check.get("name") in {"topology_ok", "geometry_valid", "lot_count", "road_width_check", "edge_shifted"}:
                        pass

                self.tx.step(tx.transaction_id, step_id, "done")
                completed_steps.add(step_id)
                step_results.append(
                    {
                        "step_id": step_id,
                        "status": "done",
                        "duration_ms": 1,
                        "op": op,
                        "algorithm": algorithm,
                        "adapter_result": algorithm_result,
                    }
                )

            if payload.get("dry_run", False):
                self.tx.rollback(tx.transaction_id)
                status = "rolled_back"
            else:
                self.tx.commit(tx.transaction_id)
                status = "committed"

            artifacts = self.artifacts.bind_execution_artifacts(plan["plan_id"], tx.transaction_id, step_results)
        except MCPQGISError:
            self.tx.rollback(tx.transaction_id)
            raise
        finally:
            self.locks.release_scope("project:current", session_id=session_id)

        if self.state.project:
            self.state.project.active_transaction = tx.transaction_id
            self.state.project.dirty = status == "committed"

        return {
            "plan_id": plan["plan_id"],
            "transaction_id": tx.transaction_id,
            "status": status,
            "step_results": step_results,
            "artifacts": artifacts,
        }

    def tool_execute_code(self, payload: dict[str, Any], role: str, **_: Any) -> dict[str, Any]:
        if not self.settings.enable_execute_code:
            raise PreconditionError(
                "execute_code is disabled by policy",
                {"setting": "MCP_ENABLE_EXECUTE_CODE", "enabled": False},
            )
        if role != "admin":
            raise PreconditionError("Only admin can use execute_code", {"role": role})
        code = payload.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ValidationError("code is required", {"field": "payload.code"})

        local_scope: dict[str, Any] = {"result": None}
        safe_globals = {"__builtins__": {"len": len, "min": min, "max": max, "sum": sum}}
        exec(code, safe_globals, local_scope)  # noqa: S102
        return {"result": local_scope.get("result")}

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
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def tool_variant_compare(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        variant_ids = payload.get("variant_ids")
        metrics = payload.get("metrics")
        if not isinstance(variant_ids, list) or len(variant_ids) < 2:
            raise ValidationError("variant_ids must contain at least two items", {"field": "payload.variant_ids"})
        if not isinstance(metrics, dict) or not metrics:
            raise ValidationError("metrics is required", {"field": "payload.metrics"})

        s = sum(float(v) for v in metrics.values())
        if s <= 0:
            raise ValidationError("metrics weights sum must be > 0", {"metrics": metrics})
        weights = {k: float(v) / s for k, v in metrics.items()}

        variant_metrics = payload.get("variant_metrics", {})
        result = compare_variants(variant_ids=variant_ids, weights=weights, variant_metrics=variant_metrics)

        out_dir = self.artifacts.base / "variant-reports"
        json_path, md_path = write_variant_report(result, out_dir)

        return {
            "winner_variant_id": result["winner_variant_id"],
            "scores": result["scores"],
            "report_path": str(md_path),
            "report_json_path": str(json_path),
        }

    def tool_git_snapshot(self, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        message = payload.get("message")
        if not message:
            raise ValidationError("message is required", {"field": "payload.message"})

        repo = Path(payload.get("repo_path", Path.cwd()))
        if not (repo / ".git").exists():
            raise NotFoundError("Not a git repository", {"repo_path": str(repo)})

        status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True)
        dirty = bool(status_proc.stdout.strip())
        if not dirty:
            rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
            return {"commit": rev.stdout.strip(), "branch": branch.stdout.strip(), "created": False, "dirty": False}

        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True, text=True)
        commit_proc = subprocess.run(["git", "commit", "-m", message], cwd=repo, check=False, capture_output=True, text=True)

        stderr = commit_proc.stderr.lower()
        stdout = commit_proc.stdout.lower()
        if commit_proc.returncode != 0 and "nothing to commit" not in stderr and "nothing to commit" not in stdout:
            raise MCPQGISError("git commit failed", {"stderr": commit_proc.stderr.strip()})

        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
        return {"commit": rev.stdout.strip(), "branch": branch.stdout.strip(), "created": True, "dirty": True}

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

        exports = self.artifacts.export(targets=targets, out_format=out_format, path=Path(out_path))

        plan_id = payload.get("plan_id", "manual-export")
        transaction_id = payload.get("transaction_id", "none")
        bind_dir = self.artifacts.plan_dir(plan_id, transaction_id)
        bind_file = bind_dir / "export-bindings.json"
        bind_file.write_text(json.dumps({"exports": exports}, indent=2), encoding="utf-8")

        return {"exports": exports, "bindings_path": str(bind_file)}

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
