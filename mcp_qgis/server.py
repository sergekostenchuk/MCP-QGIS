from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
import json
import logging

from .config import load_settings, ensure_runtime_dirs
from .envelope import EnvelopeValidator, success_envelope, error_envelope
from .errors import MCPQGISError
from .core.state import RuntimeState
from .core.sessions import SessionManager
from .core.locks import LockManager
from .core.transactions import TransactionManager
from .core.plan import PlanValidator
from .tools.dispatcher import ToolDispatcher
from .logging_utils import configure_logging, RequestContextFilter


logger = logging.getLogger("mcp_qgis.server")


def create_app_components() -> dict[str, Any]:
    settings = load_settings()
    configure_logging(settings.log_level)
    logging.getLogger().addFilter(RequestContextFilter())
    ensure_runtime_dirs(settings)

    root = Path(__file__).resolve().parents[1]
    schema_path = root / "schemas" / "mcp-tools.schema.json"
    plan_schema = root / "PLAN-IR-SCHEMA.json"

    envelope_validator = EnvelopeValidator(schema_path=schema_path, expected_api_version=settings.api_version)
    dispatcher = ToolDispatcher(
        settings=settings,
        state=RuntimeState(),
        sessions=SessionManager(),
        locks=LockManager(),
        tx=TransactionManager(),
        plan_validator=PlanValidator(plan_schema),
    )
    return {"settings": settings, "validator": envelope_validator, "dispatcher": dispatcher}


class MCPQGISHandler(BaseHTTPRequestHandler):
    components = None

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            settings = self.components["settings"]
            logger.info("healthcheck", extra={"request_id": "-", "session_id": "-", "transaction_id": "-"})
            self._json(200, {"status": "ok", "api_version": settings.api_version, "profile": settings.profile})
            return
        self._json(404, {"status": "error", "message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/tool":
            self._json(404, {"status": "error", "message": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw)
            self.components["validator"].validate(data)
            tool = data["tool"]
            payload = data["payload"]
            request_id = data["request_id"]
            session_id = data["session_id"]
            result = self.components["dispatcher"].handle(tool, payload, request_id=request_id, session_id=session_id)
            logger.info(
                "tool handled",
                extra={"request_id": request_id, "session_id": session_id, "transaction_id": "-"},
            )
            response = success_envelope(self.components["settings"].api_version, request_id, result)
            self._json(200, response)
        except MCPQGISError as err:
            ep = err.to_payload()
            rid = "unknown"
            if isinstance(locals().get("data"), dict):
                rid = data.get("request_id", "unknown")
            response = error_envelope(
                self.components["settings"].api_version,
                rid,
                ep.code,
                ep.message,
                ep.details,
                ep.retryable,
            )
            self._json(400, response)
        except json.JSONDecodeError:
            self._json(400, {"status": "error", "message": "invalid json"})
        except Exception as exc:  # noqa: BLE001
            rid = "unknown"
            if isinstance(locals().get("data"), dict):
                rid = data.get("request_id", "unknown")
            response = error_envelope(
                self.components["settings"].api_version,
                rid,
                "E_INTERNAL",
                "Unhandled server error",
                {"error": str(exc)},
                False,
            )
            self._json(500, response)


def run_server() -> None:
    components = create_app_components()
    settings = components["settings"]
    MCPQGISHandler.components = components
    httpd = HTTPServer((settings.host, settings.port), MCPQGISHandler)
    print(f"MCP-QGIS server listening on http://{settings.host}:{settings.port}")
    httpd.serve_forever()
