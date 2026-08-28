#!/usr/bin/env python3
"""AMP session: set up Ray base and NIM engine virtual environments."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAY_ROOT = PROJECT_ROOT / "cai" / "ray"


def main() -> int:
    scripts = [
        RAY_ROOT / "cai_integration" / "setup_environment.py",
        RAY_ROOT / "cai_integration" / "setup_nim_env.py",
    ]
    python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)

    for script in scripts:
        print(f"Running {script}...")
        subprocess.run([str(python), str(script)], check=True, cwd=str(RAY_ROOT))
    print("✅ Ray environments ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
