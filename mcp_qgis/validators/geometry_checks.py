from __future__ import annotations

from typing import Any


def topology_summary_from_payload(payload: dict[str, Any]) -> dict[str, int]:
    summary = payload.get("summary") or {}
    return {
        "self_intersections": int(summary.get("self_intersections", 0)),
        "overlaps": int(summary.get("overlaps", 0)),
        "gaps": int(summary.get("gaps", 0)),
    }


def evaluate_topology(summary: dict[str, int]) -> tuple[bool, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if summary["self_intersections"] > 0:
        issues.append({"rule_id": "R-TOPO-SELF", "severity": "hard", "message": "Self intersections detected"})
    if summary["overlaps"] > 0:
        issues.append({"rule_id": "R-TOPO-OVERLAP", "severity": "hard", "message": "Overlaps detected"})
    if summary["gaps"] > 0:
        issues.append({"rule_id": "R-TOPO-GAP", "severity": "hard", "message": "Gaps detected"})
    valid = len([i for i in issues if i["severity"] == "hard"]) == 0
    return valid, issues


def evaluate_lot_constraints(
    lot_metrics: list[dict[str, Any]], min_area_m2: float, require_road_access: bool, min_frontage_m: float = 0.0
) -> tuple[bool, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    for lot in lot_metrics:
        lot_id = lot.get("lot_id", "unknown")
        area = float(lot.get("area_m2", 0))
        road_access = bool(lot.get("road_access", False))
        frontage = float(lot.get("frontage_m", 0))
        if area < min_area_m2:
            issues.append(
                {
                    "rule_id": "R-AREA-001",
                    "severity": "hard",
                    "lot_id": lot_id,
                    "message": f"Lot area below minimum ({area} < {min_area_m2})",
                }
            )
        if require_road_access and not road_access:
            issues.append(
                {
                    "rule_id": "R-ROAD-001",
                    "severity": "hard",
                    "lot_id": lot_id,
                    "message": "Road access missing",
                }
            )
        if min_frontage_m > 0 and frontage < min_frontage_m:
            issues.append(
                {
                    "rule_id": "R-FRONT-001",
                    "severity": "hard",
                    "lot_id": lot_id,
                    "message": f"Frontage below minimum ({frontage} < {min_frontage_m})",
                }
            )
    valid = len([i for i in issues if i["severity"] == "hard"]) == 0
    return valid, issues
