#!/usr/bin/env python3
"""CAI Job entry point for launching the Content Localization Ray cluster."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
    ray_root = project_root / "cai" / "ray"
    script_dir = ray_root / "cai_integration"
    venv_python = project_root / ".venv" / "bin" / "python"
    launcher = script_dir / "launch_ray_cluster.py"

    if not venv_python.exists():
        print(f"❌ Virtual environment not found at {venv_python}")
        return 1
    if not launcher.exists():
        print(f"❌ Launcher not found at {launcher}")
        return 1

    print("=" * 70)
    print("🚀 Content Localization Ray Cluster Launch")
    print("=" * 70)
    print(f"Project root: {project_root}")
    print(f"Ray root: {ray_root}")

    result = subprocess.run(
        [str(venv_python), "-u", str(launcher), *sys.argv[1:]],
        cwd=str(ray_root),
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
