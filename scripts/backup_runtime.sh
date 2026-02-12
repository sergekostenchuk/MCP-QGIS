#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="${1:-runtime}"
OUT_DIR="${2:-runtime/backups}"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/mcp-qgis-runtime-$TS.tar.gz"

ABS_RUNTIME="$(cd "$(dirname "$RUNTIME_DIR")" && pwd)/$(basename "$RUNTIME_DIR")"
PARENT_DIR="$(dirname "$ABS_RUNTIME")"
BASE_DIR="$(basename "$ABS_RUNTIME")"

tar -czf "$ARCHIVE" -C "$PARENT_DIR" "$BASE_DIR"

echo "$ARCHIVE"
