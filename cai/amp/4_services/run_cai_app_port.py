#!/usr/bin/env python3
"""Minimal HTTP listener on CDSW_APP_PORT so CAI marks the application as reachable."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class _Handler(BaseHTTPRequestHandler):
    service_label: str = "service"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        body = json.dumps({"status": "ok", "service": self.service_label}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_daemon(*, port: int, service_label: str, log_path: Path | None = None) -> subprocess.Popen[bytes]:
    """Start app-port probe in the background; returns the Popen handle."""
    project = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
    script = project / "cai" / "amp" / "4_services" / "run_cai_app_port.py"
    log = log_path or (project / "cai" / "config" / f"{service_label}_app_port.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log, "ab")  # noqa: SIM115
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(script), "--port", str(port), "--service-label", service_label],
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"CAI app port probe on 127.0.0.1:{port} (log: {log})", flush=True)
    return proc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("CDSW_APP_PORT", "8100")))
    parser.add_argument("--service-label", default="app")
    args = parser.parse_args()

    _Handler.service_label = args.service_label
    server = HTTPServer(("127.0.0.1", args.port), _Handler)
    print(f"Listening on 127.0.0.1:{args.port} ({args.service_label})", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
