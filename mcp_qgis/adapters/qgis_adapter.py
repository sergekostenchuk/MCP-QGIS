from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import shutil
import socket
import subprocess
import time

from ..errors import ValidationError, PreconditionError, MCPQGISError


GEO_ALGORITHMS = {
    "native:splitwithlines",
    "native:fixgeometries",
    "native:snapgeometries",
    "native:difference",
    "native:intersection",
    "native:translategeometry",
    "native:offsetline",
    "native:buffer",
    "native:polygonstolines",
    "native:lineintersections",
    "native:multiparttosingleparts",
    "native:extractbylocation",
}


def is_metric_crs(crs: str) -> bool:
    if not crs.startswith("EPSG:"):
        return False
    code = crs.split(":", 1)[1]
    # Known geographic EPSG that are not metric by default.
    if code in {"4326", "4258", "4269"}:
        return False
    return True


@dataclass
class QGISAdapter:
    """Adapter for QGIS operations.

    Modes:
    - mode_a_plugin_bridge: placeholder bridge path for desktop-linked operations.
    - mode_b_qgis_process: headless processing via qgis_process.
    - mock: deterministic no-op/simulated output.
    """

    mode: str = "mock"
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 9876
    timeout_sec: int = 30
    max_attempts: int = 2
    retry_backoff_sec: float = 0.5
    allowlist: set[str] | None = None

    def __post_init__(self) -> None:
        if self.allowlist is None:
            self.allowlist = set(GEO_ALGORITHMS)

    @staticmethod
    def default_qgis_process_bin() -> str:
        env_bin = os.getenv("QGIS_PROCESS_BIN")
        if env_bin:
            return env_bin
        candidates = [
            "/Applications/QGIS.app/Contents/MacOS/qgis_process",
            shutil.which("qgis_process") or "",
        ]
        for c in candidates:
            if c and Path(c).exists():
                return c
        return "qgis_process"

    def run_algorithm(self, algorithm: str, parameters: dict[str, Any], crs: str = "EPSG:32637") -> dict[str, Any]:
        if algorithm not in self.allowlist:
            raise PreconditionError("Algorithm is not in allowlist", {"algorithm": algorithm})

        if algorithm in GEO_ALGORITHMS and not is_metric_crs(crs):
            raise ValidationError("Metric CRS is required for geometry operation", {"crs": crs, "algorithm": algorithm})

        if self.mode == "mock":
            return {
                "algorithm": algorithm,
                "parameters": parameters,
                "mode": self.mode,
                "status": "simulated",
                "attempts": 1,
            }

        if self.mode == "mode_a_plugin_bridge":
            bridge_response = self.bridge_request("run_algorithm", {"algorithm": algorithm, "parameters": parameters})
            return {
                "algorithm": algorithm,
                "parameters": parameters,
                "mode": self.mode,
                "status": str(bridge_response.get("status", "ok")),
                "attempts": int(bridge_response.get("attempts", 1)),
                "result": bridge_response,
            }

        if self.mode == "mode_b_qgis_process":
            return self._run_qgis_process(algorithm, parameters)

        raise PreconditionError("Unsupported adapter mode", {"mode": self.mode})

    def open_project(self, project_path: str, read_only: bool = False) -> dict[str, Any]:
        if self.mode == "mock":
            return {
                "status": "simulated",
                "project_path": project_path,
                "read_only": read_only,
                "crs": "EPSG:32637",
                "layer_count": 1,
            }
        if self.mode != "mode_a_plugin_bridge":
            raise PreconditionError("open_project requires mode_a_plugin_bridge", {"mode": self.mode})
        return self.bridge_request("open_project", {"project_path": project_path, "read_only": read_only})

    def project_state(self) -> dict[str, Any]:
        if self.mode == "mock":
            return {
                "status": "simulated",
                "project_path": None,
                "crs": "EPSG:32637",
                "dirty": False,
                "layer_count": 1,
            }
        if self.mode != "mode_a_plugin_bridge":
            raise PreconditionError("project_state requires mode_a_plugin_bridge", {"mode": self.mode})
        return self.bridge_request("project_state", {})

    def layer_catalog(self) -> dict[str, Any]:
        if self.mode == "mock":
            return {
                "status": "simulated",
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
                ],
            }
        if self.mode != "mode_a_plugin_bridge":
            raise PreconditionError("layer_catalog requires mode_a_plugin_bridge", {"mode": self.mode})
        return self.bridge_request("layer_catalog", {})

    def bridge_request(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.mode != "mode_a_plugin_bridge":
            raise PreconditionError("Bridge request requires mode_a_plugin_bridge", {"mode": self.mode})
        return self._call_plugin_bridge(action, payload)

    def _run_qgis_process(self, algorithm: str, parameters: dict[str, Any]) -> dict[str, Any]:
        bin_path = self.default_qgis_process_bin()
        attempts = 0
        last_error = ""

        env = os.environ.copy()
        env.setdefault("QGIS_PREFIX_PATH", "/Applications/QGIS.app")
        env.setdefault("PROJ_LIB", "/Applications/QGIS.app/Contents/Resources/proj")
        env.setdefault("GDAL_DATA", "/Applications/QGIS.app/Contents/Resources/gdal")

        cmd = [bin_path, "run", algorithm, "--json", json.dumps(parameters)]
        while attempts < self.max_attempts:
            attempts += 1
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                    env=env,
                    check=False,
                )
                if proc.returncode == 0:
                    out = proc.stdout.strip()
                    parsed: dict[str, Any]
                    if out:
                        try:
                            parsed = json.loads(out)
                        except json.JSONDecodeError:
                            parsed = {"raw": out}
                    else:
                        parsed = {}
                    return {
                        "algorithm": algorithm,
                        "mode": self.mode,
                        "attempts": attempts,
                        "status": "ok",
                        "result": parsed,
                    }
                last_error = proc.stderr.strip() or proc.stdout.strip() or "qgis_process failed"
            except subprocess.TimeoutExpired:
                last_error = "qgis_process timeout"

            if attempts < self.max_attempts:
                time.sleep(self.retry_backoff_sec)

        raise MCPQGISError(
            "qgis_process execution failed",
            {"algorithm": algorithm, "attempts": attempts, "error": last_error},
        )

    def _call_plugin_bridge(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = 0
        last_error = ""
        request = {"action": action, **payload}

        while attempts < self.max_attempts:
            attempts += 1
            sock: socket.socket | None = None
            try:
                sock = socket.create_connection((self.bridge_host, self.bridge_port), timeout=self.timeout_sec)
                sock.settimeout(self.timeout_sec)
                payload = json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n"
                sock.sendall(payload)

                chunks: list[bytes] = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    if b"\n" in chunk:
                        break
                raw = b"".join(chunks).decode("utf-8").strip()
                if not raw:
                    last_error = "Empty response from QGIS bridge"
                else:
                    line = raw.splitlines()[0]
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError:
                        parsed = {"raw": line}

                    status = str(parsed.get("status", "ok"))
                    if status not in {"ok", "simulated"}:
                        last_error = str(parsed.get("error") or parsed.get("message") or "bridge returned error status")
                    else:
                        parsed["attempts"] = attempts
                        return parsed
            except (OSError, TimeoutError) as exc:
                last_error = str(exc)
            finally:
                if sock is not None:
                    sock.close()

            if attempts < self.max_attempts:
                time.sleep(self.retry_backoff_sec)

        raise MCPQGISError(
            "plugin bridge execution failed",
            {
                "action": action,
                "host": self.bridge_host,
                "port": self.bridge_port,
                "attempts": attempts,
                "error": last_error,
            },
        )
