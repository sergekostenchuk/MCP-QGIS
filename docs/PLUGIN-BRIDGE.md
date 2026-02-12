# QGIS Plugin Bridge

This plugin allows MCP-QGIS server to control an open QGIS session via TCP JSON bridge.

## Location

Plugin source:

- `qgis_plugin/mcp_qgis_bridge/`

## Install (manual)

1. Copy folder `qgis_plugin/mcp_qgis_bridge` into QGIS profile plugins directory.
   macOS default:

```bash
~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/
```

2. Restart QGIS.
3. Enable plugin `MCP QGIS Bridge` in Plugin Manager.
4. Plugin starts bridge server automatically on `127.0.0.1:9876`.

## Bridge protocol

Single-line JSON requests, single-line JSON responses.

Supported actions:

- `ping`
- `open_project`
- `project_state`
- `layer_catalog`
- `run_algorithm`

Example request:

```json
{"action":"project_state"}
```

## Smoke check

```bash
python3 scripts/bridge_smoke.py --host 127.0.0.1 --port 9876
```

Optional `native:fixgeometries` check (requires valid input layer/source visible in QGIS):

```bash
python3 scripts/bridge_smoke.py --host 127.0.0.1 --port 9876 --run-fix --input <layer_id_or_source>
```

## MCP usage

Use `adapter_mode=mode_a_plugin_bridge` and optional bridge host/port in tool payload.

```json
{
  "adapter_mode": "mode_a_plugin_bridge",
  "bridge": {
    "host": "127.0.0.1",
    "port": 9876
  }
}
```
