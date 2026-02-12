from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_settings, ensure_runtime_dirs
from .server import run_server


def cmd_check_config() -> int:
    settings = load_settings()
    ensure_runtime_dirs(settings)
    print("Config OK")
    print(f"api_version={settings.api_version}")
    print(f"profile={settings.profile}")
    print(f"data_root={settings.data_root}")
    print(f"host={settings.host}")
    print(f"port={settings.port}")
    return 0


def cmd_doctor() -> int:
    settings = load_settings()
    ensure_runtime_dirs(settings)
    checks = []

    checks.append(("data_root_exists", settings.data_root.exists()))
    checks.append(("schemas_exists", (Path(__file__).resolve().parents[1] / "schemas" / "mcp-tools.schema.json").exists()))
    checks.append(("plan_schema_exists", (Path(__file__).resolve().parents[1] / "PLAN-IR-SCHEMA.json").exists()))

    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"{'OK' if ok else 'FAIL'} {name}")

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="mcp-qgis")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("check-config")
    sub.add_parser("doctor")

    args = parser.parse_args()
    if args.cmd == "run":
        run_server()
        return 0
    if args.cmd == "check-config":
        return cmd_check_config()
    if args.cmd == "doctor":
        return cmd_doctor()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
