from __future__ import annotations

from typing import Any, Callable

from .errors import ValidationError


LayerResolver = Callable[[str], str]


class PlanStepMapper:
    """Map logical Plan IR step params to concrete QGIS Processing params."""

    def map_step(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        op = str(step.get("op", "")).strip().lower()
        mapper = {
            "fix": self._map_fix,
            "split": self._map_split,
            "buffer": self._map_buffer,
            "difference": self._map_difference,
            "intersection": self._map_intersection,
            "snap": self._map_snap,
            "move": self._map_move,
        }.get(op)

        if mapper is None:
            # For non-geometry ops (validate/commit/rollback) caller won't execute algorithm.
            return dict(step.get("params", {}))

        return mapper(step, resolve_layer, default_output)

    def _map_fix(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        in_layer = self._resolve_input_layer(step, resolve_layer)
        params = dict(step.get("params", {}))
        return {
            "INPUT": in_layer,
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _map_split(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        in_layer = self._resolve_input_layer(step, resolve_layer)
        inputs = step.get("inputs", {})
        params = dict(step.get("params", {}))

        splitter_ref = inputs.get("splitter") or params.get("splitter_layer") or params.get("LINES") or "road_axis"
        splitter = resolve_layer(str(splitter_ref))

        return {
            "INPUT": in_layer,
            "LINES": splitter,
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _map_buffer(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        in_layer = self._resolve_input_layer(step, resolve_layer)
        params = dict(step.get("params", {}))
        distance = params.get("distance_m", params.get("DISTANCE"))
        if distance is None:
            raise ValidationError("buffer step requires distance_m", {"step_id": step.get("step_id")})

        return {
            "INPUT": in_layer,
            "DISTANCE": float(distance),
            "SEGMENTS": int(params.get("SEGMENTS", 5)),
            "END_CAP_STYLE": int(params.get("END_CAP_STYLE", 0)),
            "JOIN_STYLE": int(params.get("JOIN_STYLE", 0)),
            "MITER_LIMIT": float(params.get("MITER_LIMIT", 2.0)),
            "DISSOLVE": bool(params.get("DISSOLVE", False)),
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _map_difference(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        in_layer, overlay = self._resolve_overlay_inputs(step, resolve_layer)
        params = dict(step.get("params", {}))
        return {
            "INPUT": in_layer,
            "OVERLAY": overlay,
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _map_intersection(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        in_layer, overlay = self._resolve_overlay_inputs(step, resolve_layer)
        params = dict(step.get("params", {}))
        return {
            "INPUT": in_layer,
            "OVERLAY": overlay,
            "INPUT_FIELDS": params.get("INPUT_FIELDS", []),
            "OVERLAY_FIELDS": params.get("OVERLAY_FIELDS", []),
            "OVERLAY_FIELDS_PREFIX": params.get("OVERLAY_FIELDS_PREFIX", ""),
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _map_snap(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        inputs = step.get("inputs", {})
        params = dict(step.get("params", {}))
        input_ref = inputs.get("layer") or params.get("INPUT")
        if not input_ref:
            raise ValidationError("snap step requires inputs.layer", {"step_id": step.get("step_id")})

        ref_ref = inputs.get("reference") or params.get("reference_layer") or params.get("REFERENCE_LAYER") or input_ref
        tolerance = params.get("tol_m", params.get("TOLERANCE", 0.02))

        return {
            "INPUT": resolve_layer(str(input_ref)),
            "REFERENCE_LAYER": resolve_layer(str(ref_ref)),
            "TOLERANCE": float(tolerance),
            "BEHAVIOR": int(params.get("BEHAVIOR", params.get("behavior", 0))),
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _map_move(self, step: dict[str, Any], resolve_layer: LayerResolver, default_output: str) -> dict[str, Any]:
        in_layer = self._resolve_input_layer(step, resolve_layer)
        params = dict(step.get("params", {}))

        distance = params.get("distance_m", 0.0)
        dx = float(params.get("delta_x", -float(distance)))
        dy = float(params.get("delta_y", 0.0))

        return {
            "INPUT": in_layer,
            "DELTA_X": dx,
            "DELTA_Y": dy,
            "DELTA_Z": float(params.get("DELTA_Z", 0.0)),
            "DELTA_M": float(params.get("DELTA_M", 0.0)),
            "OUTPUT": str(params.get("OUTPUT", params.get("output", default_output))),
        }

    def _resolve_overlay_inputs(self, step: dict[str, Any], resolve_layer: LayerResolver) -> tuple[str, str]:
        inputs = step.get("inputs", {})
        params = dict(step.get("params", {}))
        input_ref = inputs.get("layer") or params.get("INPUT")
        overlay_ref = inputs.get("overlay") or params.get("overlay_layer") or params.get("OVERLAY")
        if not input_ref:
            raise ValidationError("step requires inputs.layer", {"step_id": step.get("step_id")})
        if not overlay_ref:
            raise ValidationError("step requires overlay input", {"step_id": step.get("step_id")})
        return resolve_layer(str(input_ref)), resolve_layer(str(overlay_ref))

    def _resolve_input_layer(self, step: dict[str, Any], resolve_layer: LayerResolver) -> str:
        inputs = step.get("inputs", {})
        params = dict(step.get("params", {}))
        input_ref = inputs.get("layer") or params.get("INPUT")
        if not input_ref:
            raise ValidationError("step requires inputs.layer", {"step_id": step.get("step_id")})
        return resolve_layer(str(input_ref))
