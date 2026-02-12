#!/usr/bin/env bash
set -euo pipefail

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-8765}"
BASE_URL="http://$HOST:$PORT"
PY_BIN="${PY_BIN:-}"

if [[ -z "$PY_BIN" ]]; then
  if command -v python >/dev/null 2>&1; then
    PY_BIN="python"
  else
    PY_BIN="python3"
  fi
fi

"$PY_BIN" -m mcp_qgis.cli check-config >/dev/null
"$PY_BIN" -m mcp_qgis.cli doctor >/dev/null

"$PY_BIN" -m mcp_qgis.cli run >/tmp/mcp-qgis-smoke.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID >/dev/null 2>&1 || true' EXIT

for _ in {1..20}; do
  if curl -sf "$BASE_URL/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

curl -sf "$BASE_URL/health" | grep '"status": "ok"' >/dev/null

REQ='{"api_version":"1.0.0","request_id":"a233a6ea-2819-4526-a71a-321c61d5f7f5","session_id":"e8f1dbf3-6ec0-492f-8d2d-f1979bbd7540","tool":"project_state","payload":{}}'
RESPONSE=$(curl -s -X POST "$BASE_URL/tool" -H 'Content-Type: application/json' -d "$REQ")

echo "$RESPONSE" | grep '"status": "error"' >/dev/null

echo "smoke:ok"
