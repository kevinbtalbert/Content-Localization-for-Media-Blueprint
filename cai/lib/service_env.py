"""Environment setup for running blueprint services natively on CAI."""

from __future__ import annotations

import os
import shlex
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


def write_service_launcher_env() -> Path:
    """Write shell exports for exec'd Python services (subprocess cannot export env)."""
    configure_python_env()
    load_config_defaults()
    path = PROJECT_ROOT / "cai" / "config" / "service_launcher.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    export_keys = (
        "PYTHONPATH",
        "AI4M_LOG_LEVEL",
        "S2S_SERVICE",
        "NGC_API_KEY",
        "ELEVENLABS_API_KEY",
        "CAMB_API_KEY",
        "S2S_DEFAULT_SOURCE_LANGUAGE",
        "S2S_DEFAULT_TARGET_LANGUAGE",
    )
    lines = ["# Generated for CAI service launchers — do not edit"]
    for key in export_keys:
        value = os.environ.get(key)
        if value is not None and value != "":
            lines.append(f"export {key}={shlex.quote(value)}")
    path.write_text("\n".join(lines) + "\n")
    return path


def require_generated_protos() -> None:
    marker = PROJECT_ROOT / "protos" / "generated" / "nvidia" / "ai4m" / "s2s" / "v1" / "s2s_pb2.py"
    if not marker.is_file():
        raise RuntimeError(
            "Generated protobuf code is missing under protos/generated/. "
            "Run AMP step 1 (Install Python Dependencies) in this project."
        )
