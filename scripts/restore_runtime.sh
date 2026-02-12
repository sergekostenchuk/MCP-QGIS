#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="${1:-}"
TARGET_DIR="${2:-.}"

if [[ -z "$ARCHIVE" ]]; then
  echo "Usage: $0 <backup.tar.gz> [target_dir]" >&2
  exit 1
fi

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Archive not found: $ARCHIVE" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
tar -xzf "$ARCHIVE" -C "$TARGET_DIR"

echo "restored:$TARGET_DIR"
