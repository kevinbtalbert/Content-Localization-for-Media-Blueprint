#!/usr/bin/env python3
"""CML Application: Controller gRPC orchestration service."""

from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.cai_common import apply_dotenv_to_os, write_dotenv_file  # noqa: E402
from cai.lib.paths import ENDPOINTS_ENV  # noqa: E402
from cai.lib.service_env import configure_python_env, load_config_defaults  # noqa: E402


def main() -> int:
    configure_python_env()
    load_config_defaults()
    apply_dotenv_to_os(ENDPOINTS_ENV)

    host = os.environ.get("CDSW_IP_ADDRESS", "127.0.0.1")
    port = os.environ.get("CONTROLLER_GRPC_API_PORT", "50056")
    service_uri = f"{host}:{port}"

    python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)

    cmd = [
        str(python),
        str(PROJECT_ROOT / "src" / "controller_service" / "entrypoint.py"),
        "--service-uri",
        service_uri,
        "--max-concurrency",
        os.environ.get("CONTROLLER_MAX_CONCURRENCY", "1"),
        "--concurrency-mode",
        os.environ.get("CONTROLLER_GRPC_CONCURRENCY_MODE", "threading"),
        "--threads-per-process",
        os.environ.get("CONTROLLER_GRPC_THREADS_PER_PROCESS", "1"),
        "--s2s-server",
        os.environ["S2S_SERVER"],
        "--lipsync-server",
        os.environ["LIPSYNC_SERVER"],
    ]

    if os.environ.get("ASD_SERVER"):
        cmd.extend(["--asd-server", os.environ["ASD_SERVER"]])

    controller_endpoint = f"{host}:{port}"
    endpoints = apply_dotenv_to_os(ENDPOINTS_ENV) if ENDPOINTS_ENV.exists() else {}
    endpoints["CONTROLLER_SERVER"] = controller_endpoint
    write_dotenv_file(ENDPOINTS_ENV, endpoints)

    controller_meta = PROJECT_ROOT / "cai" / "config" / "controller_endpoint.json"
    controller_meta.write_text(
        json.dumps({"host": host, "port": int(port), "grpc_address": controller_endpoint}, indent=2) + "\n"
    )

    print("Starting Controller:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
