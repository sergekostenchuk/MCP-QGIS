from __future__ import annotations

from http.server import HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import threading
import urllib.request
from uuid import uuid4

from mcp_qgis.server import MCPQGISHandler, create_app_components


def _json_request(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def test_http_health_and_tool_endpoint() -> None:
    with TemporaryDirectory() as td:
        old_data_root = os.environ.get("MCP_DATA_ROOT")
        os.environ["MCP_DATA_ROOT"] = td
        components = create_app_components()

        MCPQGISHandler.components = components
        server = HTTPServer(("127.0.0.1", 0), MCPQGISHandler)
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
            assert payload["status"] == "ok"

            project_path = Path(td) / "demo.qgs"
            project_path.write_text("<qgis></qgis>", encoding="utf-8")
            open_request = {
                "api_version": "1.0.0",
                "request_id": str(uuid4()),
                "session_id": str(uuid4()),
                "tool": "project_open",
                "payload": {"project_path": str(project_path)},
            }
            out = _json_request(f"http://{host}:{port}/tool", open_request)
            assert out["status"] == "ok"
            assert out["result"]["project_path"] == str(project_path)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
            if old_data_root is None:
                os.environ.pop("MCP_DATA_ROOT", None)
            else:
                os.environ["MCP_DATA_ROOT"] = old_data_root
