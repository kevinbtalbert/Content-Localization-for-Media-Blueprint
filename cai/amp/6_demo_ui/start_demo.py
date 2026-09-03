#!/usr/bin/env python3
"""CML Application: Content Localization Launchpad (Next.js UI)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from shutil import which

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402

DEMO_DIR = PROJECT_ROOT / "client" / "demos"
SERVER_JS = DEMO_DIR / "dist" / "server.js"


def _apply_saved_config() -> None:
    from cai.lib.app_config import apply_persisted_config  # noqa: WPS433

    apply_persisted_config()


def main() -> int:
    try:
        from cai.lib.cai_common import apply_dotenv_to_os  # noqa: WPS433
        from cai.lib.paths import ENDPOINTS_ENV  # noqa: WPS433
        from cai.lib.runtime_env import log_runtime_context  # noqa: WPS433

        log_runtime_context()
        _apply_saved_config()
        apply_dotenv_to_os(ENDPOINTS_ENV)
    except Exception as exc:
        print(f"WARNING: startup configuration step failed: {exc}", flush=True)

    port = os.environ.get("CDSW_APP_PORT") or os.environ.get("PORT") or "8080"
    os.environ["PORT"] = str(port)
    os.environ.setdefault("NODE_ENV", "production")
    os.environ.setdefault("OUTPUT_DIR", str(PROJECT_ROOT / "volumes" / "demo-app"))
    os.environ.setdefault("INPUT_DIR", str(PROJECT_ROOT / "assets"))

    if not SERVER_JS.is_file():
        print(
            f"ERROR: Web UI not built — missing {SERVER_JS}\n"
            "Run the AMP step 'Build Web UI' or set FORCE_DEMO_BUILD=1 and rebuild.",
            flush=True,
        )
        return 1

    node = which("node") or "/usr/bin/node"
    if not Path(node).is_file():
        print(f"ERROR: node not found (tried {node})", flush=True)
        return 1

    os.chdir(DEMO_DIR)
    print(f"Starting Launchpad UI: {node} {SERVER_JS} on 127.0.0.1:{port}", flush=True)
    return subprocess.call([node, str(SERVER_JS)])


run_amp_entry(main, __name__)
