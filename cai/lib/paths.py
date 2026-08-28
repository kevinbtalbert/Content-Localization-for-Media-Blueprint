"""Shared path helpers for CAI deployment scripts."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
RAY_ROOT = PROJECT_ROOT / "cai" / "ray"
CAI_ROOT = PROJECT_ROOT / "cai"
CONFIG_DIR = CAI_ROOT / "config"
ENDPOINTS_ENV = CONFIG_DIR / "runtime_endpoints.env"
NIM_ENDPOINTS_JSON = CAI_ROOT / "nim_endpoints.json"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
NIM_VENV_PYTHON = PROJECT_ROOT / ".venv-nim" / "bin" / "python"


def ensure_cai_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "volumes" / "models" / "lipsync").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "volumes" / "models" / "asd").mkdir(parents=True, exist_ok=True)
