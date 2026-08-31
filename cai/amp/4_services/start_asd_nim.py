#!/usr/bin/env python3
"""CAI GPU application: ASD NIM (runs inside the registered NIM runtime image)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.nim_runtime import (  # noqa: E402
    configure_asd_env,
    exec_nim_server,
    start_endpoint_publisher,
)


def main() -> int:
    config = configure_asd_env()
    print(f"ASD NIM image: {config['image']}")
    print(f"Listening on gRPC :{config['grpc_port']}, HTTP :{config['http_port']}")

    start_endpoint_publisher(
        name=config["name"],
        nim_type=config["nim_type"],
        grpc_port=config["grpc_port"],
        http_port=config["http_port"],
    )
    exec_nim_server(config["nim_type"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
