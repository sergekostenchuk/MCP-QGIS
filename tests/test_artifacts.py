from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from mcp_qgis.artifacts import ArtifactManager


def test_artifact_export_qgs_and_gpkg() -> None:
    with TemporaryDirectory() as td:
        mgr = ArtifactManager(Path(td))

        qgs_path = Path(td) / "out" / "project.qgs"
        out_qgs = mgr.export(["lots"], "qgs", qgs_path)
        assert qgs_path.exists()
        assert out_qgs[0]["path"] == str(qgs_path)

        gpkg_path = Path(td) / "out" / "result.gpkg"
        out_gpkg = mgr.export(["lots", "roads"], "gpkg", gpkg_path)
        assert gpkg_path.exists()
        assert len(out_gpkg) == 2


def test_artifact_binding_layout() -> None:
    with TemporaryDirectory() as td:
        mgr = ArtifactManager(Path(td))
        files = mgr.bind_execution_artifacts("plan-1", "tx-1", [{"step_id": "s1", "status": "done"}])
        assert any(f.endswith("step_results.json") for f in files)
        assert any(f.endswith("execution.log") for f in files)
