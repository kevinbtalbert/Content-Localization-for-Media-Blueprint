#!/usr/bin/env python3
"""CAI GPU application: LipSync NIM (runs inside the registered NIM runtime image)."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.nim_runtime import (  # noqa: E402
    configure_lipsync_env,
    run_nim_server,
    start_endpoint_publisher,
)


def main() -> int:
    config = configure_lipsync_env()
    print(f"LipSync NIM image: {config['source_image']}", flush=True)
    print(f"NIM cache dir: {config['cache_dir']}", flush=True)
    print(
        f"Listening on gRPC :{config['grpc_port']}, HTTP :{config['http_port']}",
        flush=True,
    )

    start_endpoint_publisher(
        name=config["name"],
        nim_type=config["nim_type"],
        grpc_port=config["grpc_port"],
        http_port=config["http_port"],
    )
    return run_nim_server(config["nim_type"])


if __name__ == "__main__":
    try:
        run_amp_entry(main, __name__)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(1) from None
