# Client Integration Profiles

Goal: connect model clients to MCP-QGIS and use the same tool workflow.

## Standard workflow

1. `project_open`
2. `layer_catalog`
3. `intent_to_plan`
4. `plan_preview`
5. `plan_validate`
6. `plan_execute`

For live QGIS mode include:

- `adapter_mode=mode_a_plugin_bridge`
- bridge host/port

## Codex profile

See `deploy/clients/codex-mcp.example.json`.

## Claude Code profile

See `deploy/clients/claude-code-mcp.example.json`.

## Antigravity profile

See `deploy/clients/antigravity-mcp.example.json`.

## Troubleshooting

- `Connection refused 127.0.0.1:9876`: QGIS plugin bridge is not running or wrong host/port.
- `E_PRECONDITION execute_code is disabled`: expected default policy; enable only if explicitly needed.
- `Metric CRS is required`: switch project/layer CRS to projected metric CRS (for example `EPSG:32637`) before geometry operations.
- `Algorithm is not in allowlist`: add algorithm id to allowlist file and restart MCP service.
