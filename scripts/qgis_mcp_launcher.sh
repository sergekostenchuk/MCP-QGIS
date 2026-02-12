#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
MCP_BIN="${MCP_BIN:-$PROJECT_DIR/.venv/bin/mcp-qgis}"
LOG_DIR="${LOG_DIR:-$PROJECT_DIR/runtime/logs}"
LOG_FILE="$LOG_DIR/mcp-launcher.log"
MCP_PORT="${MCP_PORT:-8765}"
QGIS_APP="${QGIS_APP:-/Applications/QGIS.app}"
QGIS_PROFILE="${QGIS_PROFILE:-default}"

mkdir -p "$LOG_DIR"

if [[ ! -x "$MCP_BIN" ]]; then
  osascript -e "display notification \"Не найден mcp-qgis: $MCP_BIN\" with title \"QGIS + MCP\""
  exit 1
fi

if [[ ! -d "$QGIS_APP" ]]; then
  osascript -e "display notification \"Не найдено приложение QGIS: $QGIS_APP\" with title \"QGIS + MCP\""
  exit 1
fi

if ! lsof -nP -iTCP:"$MCP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  nohup "$MCP_BIN" run >> "$LOG_FILE" 2>&1 &
  sleep 0.8
fi

open -a "$QGIS_APP" --args --profile "$QGIS_PROFILE"
