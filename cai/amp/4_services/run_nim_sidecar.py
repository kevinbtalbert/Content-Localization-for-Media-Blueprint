#!/usr/bin/env python3
"""Background helpers for NIM GPU apps: CAI app-port probe + endpoint metadata publish."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.nim_runtime import publish_nim_endpoint, wait_for_nim_health  # noqa: E402


class _AppPortHandler(BaseHTTPRequestHandler):
    nim_http_port: int = 8004

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        nim_ready = False
        try:
            url = f"http://127.0.0.1:{self.nim_http_port}/v1/health/ready"
            with urllib.request.urlopen(url, timeout=5) as response:
                nim_ready = response.status == 200
        except Exception:
            nim_ready = False

        body = json.dumps(
            {
                "status": "ok" if nim_ready else "starting",
                "nim_http_ready": nim_ready,
                "nim_http_port": self.nim_http_port,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve_app_port(port: int, nim_http_port: int) -> None:
    _AppPortHandler.nim_http_port = nim_http_port
    server = HTTPServer(("127.0.0.1", port), _AppPortHandler)
    print(f"CAI app port probe listening on 127.0.0.1:{port}", flush=True)
    server.serve_forever()


def _publish_after_health(*, name: str, nim_type: str, grpc_port: int, http_port: int) -> None:
    print(f"Waiting for {nim_type} NIM health on http://127.0.0.1:{http_port}/v1/health/ready ...", flush=True)
    wait_for_nim_health(http_port, timeout_s=7200)
    data = publish_nim_endpoint(name=name, nim_type=nim_type, grpc_port=grpc_port, http_port=http_port)
    print(f"Published NIM endpoint metadata for {nim_type}: {json.dumps(data[nim_type])}", flush=True)


def _log_cache_growth(cache_dir: Path, *, interval_s: int = 120) -> None:
    last_size = -1
    while True:
        if cache_dir.is_dir():
            total = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
            if total != last_size:
                mib = total / (1024 * 1024)
                print(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {cache_dir}: {mib:.1f} MiB cached", flush=True)
                last_size = total
        time.sleep(interval_s)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nim-type", required=True, choices=("lipsync", "asd"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--grpc-port", type=int, required=True)
    parser.add_argument("--http-port", type=int, required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--app-port", type=int, default=int(os.environ.get("CDSW_APP_PORT", "8100")))
    args = parser.parse_args()

    threading.Thread(
        target=_log_cache_growth,
        args=(Path(args.cache_dir),),
        daemon=True,
    ).start()
    threading.Thread(
        target=_publish_after_health,
        kwargs={
            "name": args.name,
            "nim_type": args.nim_type,
            "grpc_port": args.grpc_port,
            "http_port": args.http_port,
        },
        daemon=True,
    ).start()
    _serve_app_port(args.app_port, args.http_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
