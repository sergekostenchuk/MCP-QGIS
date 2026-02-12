from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import sqlite3

from .errors import ValidationError


class ArtifactManager:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.base = data_root / "artifacts"
        self.base.mkdir(parents=True, exist_ok=True)

    def plan_dir(self, plan_id: str, transaction_id: str | None = None) -> Path:
        path = self.base / plan_id
        if transaction_id:
            path = path / transaction_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def bind_execution_artifacts(
        self,
        plan_id: str,
        transaction_id: str,
        step_results: list[dict[str, Any]],
    ) -> list[str]:
        pdir = self.plan_dir(plan_id, transaction_id)
        step_file = pdir / "step_results.json"
        step_file.write_text(json.dumps(step_results, indent=2), encoding="utf-8")

        exec_log = pdir / "execution.log"
        exec_log.write_text("execution completed\n", encoding="utf-8")

        return [str(step_file), str(exec_log)]

    def export(self, targets: list[str], out_format: str, path: Path) -> list[dict[str, Any]]:
        path.parent.mkdir(parents=True, exist_ok=True)
        fmt = out_format.lower()

        if fmt == "geojson":
            feature_collection = {
                "type": "FeatureCollection",
                "features": [],
                "metadata": {"targets": targets},
            }
            path.write_text(json.dumps(feature_collection, indent=2), encoding="utf-8")
        elif fmt == "qgs":
            path.write_text("<qgis version=\"3.44\"></qgis>\n", encoding="utf-8")
        elif fmt == "gpkg":
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS export_meta (k TEXT, v TEXT)")
                conn.execute("DELETE FROM export_meta")
                conn.execute("INSERT INTO export_meta(k, v) VALUES (?, ?)", ("targets", ",".join(targets)))
                conn.commit()
            finally:
                conn.close()
        else:
            raise ValidationError("Unsupported export format", {"format": out_format})

        return [{"target": t, "path": str(path), "feature_count": 0} for t in targets]
