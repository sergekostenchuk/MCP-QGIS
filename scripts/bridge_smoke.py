#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import Any


def _send(host: str, port: int, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(raw)
        data = sock.recv(65536).decode("utf-8").strip()
    if not data:
        raise RuntimeError("Empty response from bridge")
    return json.loads(data.splitlines()[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check for QGIS plugin bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--run-fix", action="store_true", help="Also try native:fixgeometries")
    parser.add_argument("--input", help="INPUT layer/source for native:fixgeometries")
    args = parser.parse_args()

    ping = _send(args.host, args.port, {"action": "ping"}, args.timeout)
    if ping.get("status") != "ok":
        print(json.dumps(ping, ensure_ascii=False, indent=2))
        return 1
    print("bridge ping: ok")

    if args.run_fix:
        if not args.input:
            print("--input is required with --run-fix", file=sys.stderr)
            return 2
        fix_req = {
            "action": "run_algorithm",
            "algorithm": "native:fixgeometries",
            "parameters": {"INPUT": args.input, "OUTPUT": "memory:"},
        }
        out = _send(args.host, args.port, fix_req, args.timeout)
        if out.get("status") != "ok":
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 3
        print("bridge fixgeometries: ok")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
