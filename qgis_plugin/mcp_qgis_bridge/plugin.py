from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json
import traceback

from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QAction
from qgis.PyQt.QtNetwork import QHostAddress, QTcpServer
from qgis.core import Qgis, QgsMessageLog, QgsProject, QgsVectorLayer, QgsWkbTypes
import processing


PLUGIN_TAG = "MCPQGISBridge"


class BridgeServer(QObject):
    def __init__(self, host: str = "127.0.0.1", port: int = 9876) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self._server: QTcpServer | None = None
        self._clients: set[Any] = set()

    def start(self) -> None:
        if self._server and self._server.isListening():
            return

        server = QTcpServer(self)
        server.newConnection.connect(self._on_new_connection)
        ok = server.listen(QHostAddress(self.host), self.port)
        if not ok:
            err = server.errorString()
            raise RuntimeError(f"Bridge listen failed on {self.host}:{self.port}: {err}")

        self._server = server
        QgsMessageLog.logMessage(f"Bridge started at {self.host}:{self.port}", PLUGIN_TAG, Qgis.Info)

    def stop(self) -> None:
        if self._server is None:
            return
        for client in list(self._clients):
            try:
                client.disconnectFromHost()
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()
        self._server.close()
        self._server = None
        QgsMessageLog.logMessage("Bridge stopped", PLUGIN_TAG, Qgis.Info)

    def status(self) -> dict[str, Any]:
        listening = bool(self._server and self._server.isListening())
        return {
            "host": self.host,
            "port": self.port,
            "listening": listening,
            "clients": len(self._clients),
        }

    def _on_new_connection(self) -> None:
        if not self._server:
            return
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            self._clients.add(client)
            client.readyRead.connect(lambda c=client: self._on_ready_read(c))
            client.disconnected.connect(lambda c=client: self._on_disconnected(c))

    def _on_disconnected(self, client: Any) -> None:
        self._clients.discard(client)

    def _on_ready_read(self, client: Any) -> None:
        while client.canReadLine():
            raw = bytes(client.readLine()).decode("utf-8").strip()
            if not raw:
                continue
            response = self._handle_message(raw)
            body = (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8")
            client.write(body)
            client.flush()

    def _handle_message(self, raw: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw)
            action = str(payload.get("action", "")).strip()
            if not action:
                return {"status": "error", "error": "action is required"}

            if action == "ping":
                return {
                    "status": "ok",
                    "action": action,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "qgis_version": Qgis.QGIS_VERSION,
                }

            if action == "open_project":
                project_path = str(payload.get("project_path", "")).strip()
                if not project_path:
                    return {"status": "error", "error": "project_path is required"}
                ok = QgsProject.instance().read(project_path)
                if not ok:
                    return {"status": "error", "error": "Failed to open project", "project_path": project_path}
                return {"status": "ok", **self._project_state_payload()}

            if action == "project_state":
                return {"status": "ok", **self._project_state_payload()}

            if action == "layer_catalog":
                return {"status": "ok", "layers": self._layer_catalog_payload()}

            if action == "run_algorithm":
                algorithm = str(payload.get("algorithm", "")).strip()
                parameters = payload.get("parameters", {})
                if not algorithm:
                    return {"status": "error", "error": "algorithm is required"}
                if not isinstance(parameters, dict):
                    return {"status": "error", "error": "parameters must be object"}
                result = processing.run(algorithm, parameters)
                return {"status": "ok", "algorithm": algorithm, "result": self._jsonable(result)}

            return {"status": "error", "error": f"unknown action: {action}"}
        except Exception as exc:  # noqa: BLE001
            QgsMessageLog.logMessage(f"Bridge error: {exc}\n{traceback.format_exc()}", PLUGIN_TAG, Qgis.Critical)
            return {"status": "error", "error": str(exc)}

    def _project_state_payload(self) -> dict[str, Any]:
        project = QgsProject.instance()
        return {
            "project_path": project.fileName(),
            "crs": project.crs().authid() if project.crs().isValid() else "",
            "dirty": project.isDirty(),
            "layer_count": len(project.mapLayers()),
        }

    def _layer_catalog_payload(self) -> list[dict[str, Any]]:
        layers: list[dict[str, Any]] = []
        for layer in QgsProject.instance().mapLayers().values():
            layer_info: dict[str, Any] = {
                "layer_id": layer.id(),
                "name": layer.name(),
                "source": layer.source(),
                "provider": layer.providerType() if hasattr(layer, "providerType") else "",
                "crs": layer.crs().authid() if hasattr(layer, "crs") and layer.crs().isValid() else "",
                "is_valid": bool(layer.isValid()),
                "feature_count": int(layer.featureCount()) if hasattr(layer, "featureCount") else None,
                "geometry_type": "Unknown",
                "fields": [],
            }

            if isinstance(layer, QgsVectorLayer):
                layer_info["geometry_type"] = QgsWkbTypes.displayString(layer.wkbType())
                layer_info["fields"] = [
                    {"name": field.name(), "type": field.typeName()}
                    for field in layer.fields()
                ]

            layers.append(layer_info)

        return layers

    def _jsonable(self, value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, dict):
            return {str(k): self._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._jsonable(v) for v in value]
        if hasattr(value, "id") and hasattr(value, "name"):
            try:
                return {"layer_id": value.id(), "name": value.name()}
            except Exception:  # noqa: BLE001
                return str(value)
        return str(value)


class MCPQGISBridgePlugin:
    def __init__(self, iface: Any) -> None:
        self.iface = iface
        self.server = BridgeServer()
        self.action: QAction | None = None

    def initGui(self) -> None:  # noqa: N802
        self.action = QAction("MCP QGIS Bridge: Restart", self.iface.mainWindow())
        self.action.triggered.connect(self.restart_server)
        self.iface.addPluginToMenu("MCP QGIS Bridge", self.action)
        self.start_server()

    def unload(self) -> None:
        self.stop_server()
        if self.action is not None:
            self.iface.removePluginMenu("MCP QGIS Bridge", self.action)
            self.action = None

    def start_server(self) -> None:
        self.server.start()

    def stop_server(self) -> None:
        self.server.stop()

    def restart_server(self) -> None:
        self.stop_server()
        self.start_server()
