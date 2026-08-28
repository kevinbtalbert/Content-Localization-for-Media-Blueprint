#!/usr/bin/env python3
"""AMP session: set up Ray base and NIM engine virtual environments."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.paths import PROJECT_ROOT, RAY_ROOT  # noqa: E402


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


run_amp_entry(main, __name__)
