from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass
class ParsedIntent:
    intent_type: str
    lots_target: int | None = None
    road_width_m: float | None = None
    shift_distance_m: float | None = None
    boundary_a: str | None = None
    boundary_b: str | None = None


class IntentPlanner:
    """Rule-based parser and plan templates for MVP.

    Supported intents:
    - split parcel into N lots + road width
    - shift boundary A/C by X meters
    """

    def parse(self, text: str) -> ParsedIntent:
        normalized = text.lower().strip()

        split_match = re.search(r"раздел[иья].*на\s*(\d+)", normalized)
        road_match = re.search(r"дорог[ауы].*?(\d+(?:[\.,]\d+)?)\s*м", normalized)

        shift_match = re.search(r"сдвин[ьт].*границ[ау].*?([a-zа-я0-9]+)\s*/\s*([a-zа-я0-9]+).*?(\d+(?:[\.,]\d+)?)\s*м", normalized)
        if shift_match:
            a, b, d = shift_match.groups()
            return ParsedIntent(
                intent_type="boundary_shift",
                shift_distance_m=float(d.replace(",", ".")),
                boundary_a=a.upper(),
                boundary_b=b.upper(),
            )

        if split_match:
            lots = int(split_match.group(1))
            road = float(road_match.group(1).replace(",", ".")) if road_match else None
            return ParsedIntent(intent_type="split_with_road", lots_target=lots, road_width_m=road)

        return ParsedIntent(intent_type="unknown")

    def missing_inputs(self, parsed: ParsedIntent, constraints: dict[str, Any] | None = None) -> list[str]:
        constraints = constraints or {}
        missing: list[str] = []

        if parsed.intent_type == "split_with_road":
            if parsed.lots_target is None:
                missing.append("Укажите количество участков (N).")
            if parsed.road_width_m is None and "road_width_m" not in constraints:
                missing.append("Укажите ширину дороги в метрах.")

        if parsed.intent_type == "boundary_shift":
            if parsed.shift_distance_m is None:
                missing.append("Укажите расстояние сдвига в метрах.")
            if not parsed.boundary_a or not parsed.boundary_b:
                missing.append("Укажите пару смежных участков/границ (например A/C).")

        if parsed.intent_type == "unknown":
            missing.append("Не удалось распознать команду. Уточните задачу в формате split или boundary shift.")

        return missing

    def build_plan(self, text: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
        constraints = constraints or {}
        parsed = self.parse(text)
        missing = self.missing_inputs(parsed, constraints)

        if parsed.intent_type == "split_with_road" and not missing:
            lots_target = parsed.lots_target or int(constraints.get("lots_target", 4))
            road_width_m = parsed.road_width_m or float(constraints.get("road_width_m", 6))
            return {
                "plan": {
                    "schema_version": "1.0.0",
                    "plan_id": "plan-split-road",
                    "project_id": "project-current",
                    "created_at": "2026-02-12T00:00:00Z",
                    "author": "intent-planner",
                    "intent_text": text,
                    "crs": "EPSG:32637",
                    "ruleset": "cadastre_default",
                    "idempotency_key": "auto-generated-key",
                    "context": {"lots_target": lots_target, "road_width_m": road_width_m},
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
                            "inputs": {"layer": "parcel_src", "splitter": "road_axis"},
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
                            "params": {"distance_m": road_width_m / 2.0},
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
                },
                "assumptions": [],
                "missing_inputs": [],
                "intent_type": parsed.intent_type,
            }

        if parsed.intent_type == "boundary_shift" and not missing:
            shift = parsed.shift_distance_m or float(constraints.get("shift_distance_m", 3))
            a = parsed.boundary_a or "A"
            b = parsed.boundary_b or "C"
            return {
                "plan": {
                    "schema_version": "1.0.0",
                    "plan_id": "plan-boundary-shift",
                    "project_id": "project-current",
                    "created_at": "2026-02-12T00:00:00Z",
                    "author": "intent-planner",
                    "intent_text": text,
                    "crs": "EPSG:32637",
                    "ruleset": "cadastre_default",
                    "idempotency_key": "auto-generated-key",
                    "context": {
                        "shift_distance_m": shift,
                        "boundary_a": a,
                        "boundary_b": b,
                    },
                    "constraints": constraints,
                    "steps": [
                        {
                            "step_id": "s1",
                            "op": "intersection",
                            "inputs": {"layer": f"lot_{a.lower()}", "overlay": f"lot_{b.lower()}"},
                            "params": {"boundary_pair": f"{a}/{b}"},
                            "prechecks": [],
                            "postchecks": [{"name": "common_edge_found"}],
                            "idempotent": True,
                            "retry": {"max_attempts": 1, "backoff_ms": 0},
                            "on_error": "rollback",
                            "status": "pending",
                            "depends_on": [],
                        },
                        {
                            "step_id": "s2",
                            "op": "move",
                            "inputs": {"layer": "s1"},
                            "params": {"distance_m": shift},
                            "prechecks": [],
                            "postchecks": [{"name": "edge_shifted"}],
                            "idempotent": False,
                            "retry": {"max_attempts": 1, "backoff_ms": 0},
                            "on_error": "rollback",
                            "status": "pending",
                            "depends_on": ["s1"],
                        },
                        {
                            "step_id": "s3",
                            "op": "validate",
                            "inputs": {"layer": "lots"},
                            "params": {"ruleset": "cadastre_default"},
                            "prechecks": [],
                            "postchecks": [{"name": "topology_ok"}],
                            "idempotent": True,
                            "retry": {"max_attempts": 1, "backoff_ms": 0},
                            "on_error": "rollback",
                            "status": "pending",
                            "depends_on": ["s2"],
                        },
                        {
                            "step_id": "s4",
                            "op": "commit",
                            "inputs": {},
                            "params": {},
                            "prechecks": [],
                            "postchecks": [],
                            "idempotent": True,
                            "retry": {"max_attempts": 1, "backoff_ms": 0},
                            "on_error": "rollback",
                            "status": "pending",
                            "depends_on": ["s3"],
                        },
                    ],
                },
                "assumptions": [],
                "missing_inputs": [],
                "intent_type": parsed.intent_type,
            }

        return {
            "plan": None,
            "assumptions": [],
            "missing_inputs": missing,
            "intent_type": parsed.intent_type,
        }
