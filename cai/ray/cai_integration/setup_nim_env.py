#!/usr/bin/env python3
"""CML Job: Create isolated NIM virtual environment."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
RAY_ROOT = PROJECT_ROOT / "cai" / "ray"
sys.path.insert(0, str(RAY_ROOT))

from cai_integration.setup_environment import _ENGINE_PACKAGES, setup_engine_venv  # noqa: E402

NIM_PACKAGES = _ENGINE_PACKAGES["nim"]
_VENV_DIR = "/home/cdsw/.venv-nim"


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up NIM isolated venv")
    parser.add_argument("--force", action="store_true")
    args, _ = parser.parse_known_args()

    force = args.force or os.environ.get("SETUP_FORCE_RECREATE", "").strip() in ("1", "true", "yes")
    if force and os.path.exists(_VENV_DIR):
        shutil.rmtree(_VENV_DIR, ignore_errors=True)

    if not setup_engine_venv("nim", NIM_PACKAGES):
        sys.exit(1)

    result = subprocess.run(
        [f"{_VENV_DIR}/bin/python", "-c", "import requests; print(requests.__version__)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)
    print(f"✅ NIM venv ready: requests {result.stdout.strip()}")


if __name__ == "__main__":
    main()
