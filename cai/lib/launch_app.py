"""CAI application entry helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def exec_bash_script(relative_script: str) -> None:
    """
    Replace the current process with a bash launcher script.

    CAI application scripts must use os.execv (not IPython ``!bash``) so the
    NIM / gRPC foreground process keeps the application alive and failures
    surface in Application Logs.
    """
    project = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
    script = project / relative_script
    if not script.is_file():
        raise FileNotFoundError(f"Launcher script not found: {script}")
    os.execv("/bin/bash", ["bash", str(script)])


def exec_serverless_nim_placeholder(service_label: str) -> None:
    """
    Replace the current process with a minimal app-port probe only.

    Used when ``NIM_DEPLOY_MODE=SERVERLESS`` so LipSync/ASD AMP application
    steps stay green without starting bundled GPU NIM processes.
    """
    project = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
    script = project / "cai" / "amp" / "4_services" / "run_cai_app_port.py"
    port = os.environ.get("CDSW_APP_PORT", "8100")
    print(
        f"NIM_DEPLOY_MODE=SERVERLESS — {service_label} GPU NIM not started; "
        f"holding CDSW_APP_PORT on 127.0.0.1:{port}",
        flush=True,
    )
    os.execv(
        sys.executable,
        [sys.executable, str(script), "--port", str(port), "--service-label", service_label],
    )
