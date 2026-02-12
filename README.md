# MCP-QGIS

Implementation repository for MCP + QGIS cadastre MVP.

## Current Status

- Planning documents: `PLANS/`
- MVP skeleton code: `mcp_qgis/`
- Schemas: `schemas/`, `PLAN-IR-SCHEMA.json`
- Tests: `tests/`
- Reference datasets: `testdata/`
- Deployment profiles: `deploy/profiles/`
- Ops scripts: `scripts/`

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

Run with explicit profile:

```bash
set -a
source deploy/profiles/local.env
set +a
mcp-qgis run
```

Run tests:

```bash
pytest --cov=mcp_qgis --cov-report=term-missing
```

Run smoke:

```bash
./scripts/smoke.sh
```

Backup and restore runtime:

```bash
./scripts/backup_runtime.sh runtime runtime/backups
./scripts/restore_runtime.sh runtime/backups/<archive>.tar.gz .
```
