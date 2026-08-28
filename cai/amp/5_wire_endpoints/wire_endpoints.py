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


def main() -> int:
    load_config_defaults()

    if not NIM_ENDPOINTS_JSON.exists():
        print(f"❌ Missing {NIM_ENDPOINTS_JSON} — deploy NIMs first")
        return 1

    _wait_for_file(S2S_ENDPOINT)
    nim_data = json.loads(NIM_ENDPOINTS_JSON.read_text())
    s2s_data = json.loads(S2S_ENDPOINT.read_text())

    lipsync = nim_data.get("lipsync") or nim_data.get("lipsync-nim", {})
    asd = nim_data.get("asd") or nim_data.get("asd-nim", {})

    endpoints = {
        "S2S_SERVER": s2s_data.get("grpc_address", f"{s2s_data['host']}:{s2s_data['port']}"),
        "LIPSYNC_SERVER": lipsync.get("grpc_address", f"{lipsync.get('host')}:{lipsync.get('grpc_port')}"),
        "ASD_SERVER": asd.get("grpc_address", f"{asd.get('host')}:{asd.get('grpc_port')}"),
    }

    write_dotenv_file(ENDPOINTS_ENV, endpoints)
    print("Wrote runtime endpoints:")
    for key, value in endpoints.items():
        print(f"  {key}={value}")
    return 0


run_amp_entry(main, __name__)
