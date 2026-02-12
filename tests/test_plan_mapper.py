from __future__ import annotations

from mcp_qgis.errors import ValidationError
from mcp_qgis.plan_mapper import PlanStepMapper


MAPPER = PlanStepMapper()


def _resolver(ref: str) -> str:
    return {
        "parcel_src": "layer_parcel",
        "road_axis": "layer_road_axis",
        "lot_a": "layer_lot_a",
        "lot_c": "layer_lot_c",
        "s1": "layer_tmp_s1",
    }.get(ref, ref)


def test_map_split_step() -> None:
    step = {
        "step_id": "s2",
        "op": "split",
        "inputs": {"layer": "parcel_src", "splitter": "road_axis"},
        "params": {},
    }
    out = MAPPER.map_step(step, _resolver, default_output="memory:s2")
    assert out["INPUT"] == "layer_parcel"
    assert out["LINES"] == "layer_road_axis"
    assert out["OUTPUT"] == "memory:s2"


def test_map_buffer_step_distance_required() -> None:
    step = {
        "step_id": "s3",
        "op": "buffer",
        "inputs": {"layer": "road_axis"},
        "params": {"distance_m": 3.0},
    }
    out = MAPPER.map_step(step, _resolver, default_output="memory:s3")
    assert out["INPUT"] == "layer_road_axis"
    assert out["DISTANCE"] == 3.0


def test_map_intersection_step_requires_overlay() -> None:
    step = {
        "step_id": "s1",
        "op": "intersection",
        "inputs": {"layer": "lot_a"},
        "params": {},
    }
    try:
        MAPPER.map_step(step, _resolver, default_output="memory:s1")
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_map_move_step_uses_intermediate_output() -> None:
    step = {
        "step_id": "s2",
        "op": "move",
        "inputs": {"layer": "s1"},
        "params": {"distance_m": 3},
    }
    out = MAPPER.map_step(step, _resolver, default_output="memory:s2")
    assert out["INPUT"] == "layer_tmp_s1"
    assert out["DELTA_X"] == -3.0
