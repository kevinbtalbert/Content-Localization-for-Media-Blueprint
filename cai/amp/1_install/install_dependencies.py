#!/usr/bin/env python3
"""AMP session: install Python dependencies and generate protobuf code."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    os.chdir(PROJECT_ROOT)
    print("Installing Content Localization Python dependencies...")

    if shutil_which("uv"):
        subprocess.run(["uv", "sync", "--extra", "test"], check=True)
        python = PROJECT_ROOT / ".venv" / "bin" / "python"
    else:
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        python = Path(sys.executable)

    subprocess.run(["bash", "protos/generate_protos.sh"], check=True, env={**os.environ, "PATH": os.environ.get("PATH", "")})
    print("✅ Dependencies and protobuf code ready")
    return 0


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
