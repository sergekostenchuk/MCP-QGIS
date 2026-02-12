# MCP-QGIS

Implementation repository for MCP + QGIS cadastre MVP.

## Current Status

- Planning documents: `PLANS/`
- MVP skeleton code: `mcp_qgis/`
- Schemas: `schemas/`, `PLAN-IR-SCHEMA.json`
- Tests: `tests/`
- Reference datasets: `testdata/`

## Quick Start

```bash
cd /Users/kostenchuksergey/MCP-QGIS
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Check config:

```bash
mcp-qgis check-config
mcp-qgis doctor
```

Run local server:

```bash
mcp-qgis run
# health: GET http://127.0.0.1:8765/health
# tool endpoint: POST http://127.0.0.1:8765/tool
```

Run tests:

```bash
pytest
```
