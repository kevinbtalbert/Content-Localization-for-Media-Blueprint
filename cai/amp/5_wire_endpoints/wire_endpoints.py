#!/usr/bin/env python3
"""AMP session: write runtime_endpoints.env from NIM and S2S endpoint metadata."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.cai_common import write_dotenv_file  # noqa: E402
from cai.lib.deploy_mode import (  # noqa: E402
    deploy_mode_label,
    is_serverless_nim_mode,
    serverless_runtime_endpoints,
    write_serverless_nim_endpoints_json,
)
from cai.lib.paths import ENDPOINTS_ENV, NIM_ENDPOINTS_JSON, PROJECT_ROOT  # noqa: E402
from cai.lib.service_env import load_config_defaults  # noqa: E402

S2S_ENDPOINT = PROJECT_ROOT / "cai" / "config" / "s2s_endpoint.json"


def _wait_for_file(path: Path, timeout_s: int = 300) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for {path}")


def _wait_for_nim_endpoints(timeout_s: int = 1200) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not NIM_ENDPOINTS_JSON.exists():
            time.sleep(10)
            continue
        data = json.loads(NIM_ENDPOINTS_JSON.read_text())
        lipsync = data.get("lipsync") or data.get("lipsync-nim")
        asd = data.get("asd") or data.get("asd-nim")
        if lipsync and asd:
            return
        time.sleep(10)
    raise TimeoutError(
        f"Timed out waiting for LipSync and ASD entries in {NIM_ENDPOINTS_JSON}"
    )


def _wire_serverless() -> int:
    print(f"Deployment model: {deploy_mode_label()}")
    print("Waiting for Speech-to-Speech application to publish endpoint metadata...")
    _wait_for_file(S2S_ENDPOINT)

    s2s_data = json.loads(S2S_ENDPOINT.read_text())
    nim_path = write_serverless_nim_endpoints_json()
    print(f"Wrote serverless NIM metadata: {nim_path}")

    endpoints = serverless_runtime_endpoints()
    endpoints["S2S_SERVER"] = s2s_data.get(
        "grpc_address", f"{s2s_data['host']}:{s2s_data['port']}"
    )

    write_dotenv_file(ENDPOINTS_ENV, endpoints)
    print("Wrote runtime endpoints (serverless LipSync/ASD via NVCF):")
    for key, value in endpoints.items():
        print(f"  {key}={value}")
    return 0


def _wire_bundled() -> int:
    print(f"Deployment model: {deploy_mode_label()}")
    print("Waiting for NIM GPU applications to publish endpoint metadata...")
    _wait_for_nim_endpoints()
    _wait_for_file(S2S_ENDPOINT)

    nim_data = json.loads(NIM_ENDPOINTS_JSON.read_text())
    s2s_data = json.loads(S2S_ENDPOINT.read_text())

    lipsync = nim_data.get("lipsync") or nim_data.get("lipsync-nim", {})
    asd = nim_data.get("asd") or nim_data.get("asd-nim", {})

    endpoints = {
        "S2S_SERVER": s2s_data.get("grpc_address", f"{s2s_data['host']}:{s2s_data['port']}"),
        "LIPSYNC_SERVER": lipsync.get("grpc_address", f"{lipsync.get('host')}:{lipsync.get('grpc_port')}"),
        "ASD_SERVER": asd.get("grpc_address", f"{asd.get('host')}:{asd.get('grpc_port')}"),
        "NIM_DEPLOY_MODE": "BUNDLED",
    }

    write_dotenv_file(ENDPOINTS_ENV, endpoints)
    print("Wrote runtime endpoints:")
    for key, value in endpoints.items():
        print(f"  {key}={value}")
    return 0


def main() -> int:
    load_config_defaults()
    if is_serverless_nim_mode():
        return _wire_serverless()
    return _wire_bundled()


run_amp_entry(main, __name__)
