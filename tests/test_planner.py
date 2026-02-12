from __future__ import annotations

from mcp_qgis.planner import IntentPlanner


def test_planner_split_with_road_plan() -> None:
    planner = IntentPlanner()
    out = planner.build_plan("Раздели участок на 4, дорога 6 м")
    assert out["intent_type"] == "split_with_road"
    assert out["missing_inputs"] == []
    assert out["plan"]["context"]["lots_target"] == 4
    assert out["plan"]["context"]["road_width_m"] == 6.0


def test_planner_boundary_shift_plan() -> None:
    planner = IntentPlanner()
    out = planner.build_plan("Сдвинь границу A/C на 3 м")
    assert out["intent_type"] == "boundary_shift"
    assert out["missing_inputs"] == []
    steps = [s["op"] for s in out["plan"]["steps"]]
    assert "move" in steps


def test_planner_missing_inputs_for_unknown_intent() -> None:
    planner = IntentPlanner()
    out = planner.build_plan("Сделай красиво")
    assert out["plan"] is None
    assert len(out["missing_inputs"]) >= 1
