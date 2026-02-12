from __future__ import annotations

from mcp_qgis.adapters.qgis_adapter import QGISAdapter
from mcp_qgis.errors import PreconditionError, ValidationError


def test_adapter_rejects_non_allowlist_algorithm() -> None:
    adapter = QGISAdapter(mode="mock", allowlist={"native:fixgeometries"})
    try:
        adapter.run_algorithm("native:difference", {})
        assert False, "Expected PreconditionError"
    except PreconditionError:
        assert True


def test_adapter_requires_metric_crs_for_geometry_ops() -> None:
    adapter = QGISAdapter(mode="mock")
    try:
        adapter.run_algorithm("native:buffer", {"DISTANCE": 10}, crs="EPSG:4326")
        assert False, "Expected ValidationError"
    except ValidationError:
        assert True


def test_adapter_mock_success() -> None:
    adapter = QGISAdapter(mode="mock")
    out = adapter.run_algorithm("native:fixgeometries", {"INPUT": "layer"}, crs="EPSG:32637")
    assert out["status"] == "simulated"
