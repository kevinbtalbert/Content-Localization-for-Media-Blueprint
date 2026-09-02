"""Environment setup for running blueprint services natively on CAI."""

from __future__ import annotations

import os
from pathlib import Path

from cai.lib.paths import PROJECT_ROOT


def configure_python_env() -> None:
    paths = [
        str(PROJECT_ROOT),
        str(PROJECT_ROOT / "src"),
        str(PROJECT_ROOT / "client"),
        str(PROJECT_ROOT / "protos" / "generated"),
    ]
    existing = os.environ.get("PYTHONPATH", "")
    merged = ":".join(paths + ([existing] if existing else []))
    os.environ["PYTHONPATH"] = merged
    os.environ.setdefault("AI4M_LOG_LEVEL", "INFO")


def load_config_defaults() -> None:
    """Load persisted Setup config, then optional configs/*.env fallbacks."""
    try:
        from cai.lib.app_config import apply_persisted_config

        apply_persisted_config()
    except Exception:
        pass

    service = os.environ.get("S2S_SERVICE", "EL_DUBBING")
    config_file = PROJECT_ROOT / "configs" / (
        "camb.env" if service == "CAMB_DUBBING" else "elevenlabs.env"
    )
    if not config_file.exists():
        return
    for line in config_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        os.environ.setdefault(key, value)
