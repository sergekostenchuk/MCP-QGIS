# MCP-QGIS Deployment

## Local profile (Mac + open QGIS)

1. Load env:

```bash
set -a
source deploy/profiles/local.env
set +a
```

2. Optional allowlist:

```bash
export MCP_ALLOWED_ALGORITHMS_FILE=./deploy/profiles/allowed_algorithms.txt
```

3. Start service:

```bash
python -m mcp_qgis.cli run
```

4. Healthcheck:

```bash
curl http://127.0.0.1:8765/health
```

## Server profile (headless)

1. Load env:

```bash
set -a
source deploy/profiles/server.env
set +a
```

2. Set `QGIS_PROCESS_BIN` where needed.
3. Start service with process manager (systemd/supervisor).
4. Run smoke check after deploy:

```bash
./scripts/smoke.sh
```

## Backup and Restore

Create backup:

```bash
./scripts/backup_runtime.sh runtime runtime/backups
```

Restore backup:

```bash
./scripts/restore_runtime.sh runtime/backups/<archive>.tar.gz .
```

## Update procedure

1. Create git snapshot before deploy.
2. Pull/update package.
3. Run `pytest` and `./scripts/smoke.sh`.
4. Restart service.
5. Verify `/health` and one tool call.
