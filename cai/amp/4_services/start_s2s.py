#!/usr/bin/env python3
"""CML Application: Speech-to-Speech gRPC service."""

from __future__ import annotations

import os
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.service_env import configure_python_env, load_config_defaults  # noqa: E402


def main() -> int:
    configure_python_env()
    load_config_defaults()

    service = os.environ.get("S2S_SERVICE", "EL_DUBBING")
    host = os.environ.get("CDSW_IP_ADDRESS", "127.0.0.1")
    port = os.environ.get("S2S_GRPC_API_PORT", "50050")
    os.environ["S2S_SERVER"] = f"{host}:{port}"

    endpoint_file = PROJECT_ROOT / "cai" / "config" / "s2s_endpoint.json"
    endpoint_file.parent.mkdir(parents=True, exist_ok=True)
    endpoint_file.write_text(
        json.dumps({"host": host, "port": int(port), "grpc_address": os.environ["S2S_SERVER"]}, indent=2) + "\n"
    )

    subcommand = "camb_dubbing" if service == "CAMB_DUBBING" else "el_dubbing"
    python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)

    cmd = [
        str(python),
        str(PROJECT_ROOT / "src" / "s2s_service" / "entrypoint.py"),
        subcommand,
        "--service-uri",
        os.environ["S2S_SERVER"],
        "--max-concurrency",
        os.environ.get("S2S_MAX_CONCURRENCY", "1"),
        "--concurrency-mode",
        os.environ.get("S2S_GRPC_CONCURRENCY_MODE", "threading"),
        "--threads-per-process",
        os.environ.get("S2S_GRPC_THREADS_PER_PROCESS", "1"),
        "--sample-rate-hz",
        os.environ.get("S2S_SAMPLE_RATE_HZ", "16000"),
        "--message-size",
        os.environ.get("S2S_MESSAGE_SIZE", "67108864"),
        "--default-source-language",
        os.environ.get("S2S_DEFAULT_SOURCE_LANGUAGE", "auto"),
        "--default-target-language",
        os.environ.get("S2S_DEFAULT_TARGET_LANGUAGE", "de"),
        "--audio-format",
        "MP3",
    ]
    print("Starting S2S:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
