from __future__ import annotations

import json
import socket
import threading
from typing import Any

from mcp_qgis.adapters.qgis_adapter import QGISAdapter
from mcp_qgis.errors import PreconditionError, ValidationError


def _serve_once(response: dict[str, Any]) -> tuple[str, int, dict[str, object], threading.Thread, socket.socket]:
    request_holder: dict[str, object] = {}
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    def _handler() -> None:
        conn, _ = server.accept()
        with conn:
            data = conn.recv(4096).decode("utf-8").strip()
            request_holder["raw"] = data
            conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
        server.close()

    thread = threading.Thread(target=_handler, daemon=True)
    thread.start()
    return host, port, request_holder, thread, server


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


def test_adapter_mode_a_plugin_bridge_success() -> None:
    host, port, request_holder, thread, _server = _serve_once({"status": "ok", "result": {"OUTPUT": "layer_fixed"}})
    adapter = QGISAdapter(mode="mode_a_plugin_bridge", bridge_host=host, bridge_port=port, timeout_sec=2, max_attempts=1)
    out = adapter.run_algorithm("native:fixgeometries", {"INPUT": "layer"}, crs="EPSG:32637")
    thread.join(timeout=1)

    assert out["status"] == "ok"
    raw = str(request_holder["raw"])
    assert "native:fixgeometries" in raw


def test_adapter_bridge_project_state_action() -> None:
    response = {"status": "ok", "project_path": "/tmp/demo.qgs", "crs": "EPSG:32637", "dirty": False, "layer_count": 3}
    host, port, request_holder, thread, _server = _serve_once(response)
    adapter = QGISAdapter(mode="mode_a_plugin_bridge", bridge_host=host, bridge_port=port, timeout_sec=2, max_attempts=1)
    out = adapter.project_state()
    thread.join(timeout=1)
    assert out["status"] == "ok"
    assert out["layer_count"] == 3
    assert '"action": "project_state"' in str(request_holder["raw"])
