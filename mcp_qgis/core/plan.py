from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from jsonschema import Draft202012Validator

from ..errors import ValidationError


class PlanValidator:
    def __init__(self, schema_path: Path) -> None:
        self.schema_path = schema_path
        self.validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))

    def validate(self, plan: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
        errors = []
        for err in self.validator.iter_errors(plan):
            errors.append({"message": err.message, "path": list(err.path)})
        return len(errors) == 0, errors


def build_plan_from_intent(intent_text: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    constraints = constraints or {}
    lots_target = 4
    road_width = constraints.get("road_width_m", 6)

    return {
        "schema_version": "1.0.0",
        "plan_id": "plan-generated",
        "project_id": "project-current",
        "created_at": "2026-02-12T00:00:00Z",
        "author": "intent-planner",
        "intent_text": intent_text,
        "crs": "EPSG:32637",
        "ruleset": "cadastre_default",
        "idempotency_key": "auto-generated-key",
        "context": {"lots_target": lots_target, "road_width_m": road_width},
        "constraints": constraints,
        "steps": [
            {
                "step_id": "s1",
                "op": "fix",
                "inputs": {"layer": "parcel_src"},
                "params": {},
                "prechecks": [],
                "postchecks": [{"name": "geometry_valid"}],
                "idempotent": True,
                "retry": {"max_attempts": 1, "backoff_ms": 0},
                "on_error": "rollback",
                "status": "pending",
                "depends_on": [],
            },
            {
                "step_id": "s2",
                "op": "split",
                "inputs": {"layer": "parcel_src"},
                "params": {"lots_target": lots_target},
                "prechecks": [],
                "postchecks": [{"name": "lot_count"}],
                "idempotent": False,
                "retry": {"max_attempts": 1, "backoff_ms": 0},
                "on_error": "rollback",
                "status": "pending",
                "depends_on": ["s1"],
            },
            {
                "step_id": "s3",
                "op": "buffer",
                "inputs": {"layer": "road_axis"},
                "params": {"distance_m": road_width / 2.0},
                "prechecks": [],
                "postchecks": [{"name": "road_width_check"}],
                "idempotent": False,
                "retry": {"max_attempts": 1, "backoff_ms": 0},
                "on_error": "rollback",
                "status": "pending",
                "depends_on": ["s2"],
            },
            {
                "step_id": "s4",
                "op": "validate",
                "inputs": {"layer": "lots"},
                "params": {"ruleset": "cadastre_default"},
                "prechecks": [],
                "postchecks": [{"name": "topology_ok"}],
                "idempotent": True,
                "retry": {"max_attempts": 1, "backoff_ms": 0},
                "on_error": "rollback",
                "status": "pending",
                "depends_on": ["s3"],
            },
            {
                "step_id": "s5",
                "op": "commit",
                "inputs": {},
                "params": {},
                "prechecks": [],
                "postchecks": [],
                "idempotent": True,
                "retry": {"max_attempts": 1, "backoff_ms": 0},
                "on_error": "rollback",
                "status": "pending",
                "depends_on": ["s4"],
            },
        ],
    }
