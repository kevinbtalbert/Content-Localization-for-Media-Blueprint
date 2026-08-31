"""Shared helpers for CAI AMP prerequisite validation."""

from __future__ import annotations

import os
import shutil
from typing import Iterable, Optional

# Must match ML_RUNTIME_EDITION in the root Dockerfile.
CUSTOM_RUNTIME_EDITION = "ContentLocalization"

_EXTRA_PATH_DIRS = (
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/sbin",
    "/opt/content-localization/scripts/docker",
)


def extended_path() -> str:
    parts = list(_EXTRA_PATH_DIRS)
    current = os.environ.get("PATH", "").strip()
    if current:
        parts.append(current)
    return os.pathsep.join(parts)


def find_tool(name: str, extra_candidates: Optional[Iterable[str]] = None) -> Optional[str]:
    """Locate a CLI on PATH or common absolute locations."""
    path = extended_path()
    found = shutil.which(name, path=path)
    if found:
        return found
    candidates = [f"/usr/local/bin/{name}", f"/usr/bin/{name}", f"/bin/{name}"]
    if extra_candidates:
        candidates.extend(extra_candidates)
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def get_ngc_api_key() -> str:
    """Return NGC credentials from project environment (several aliases supported)."""
    for key in ("NGC_API_KEY", "LIPSYNC_API_KEY", "ASD_API_KEY"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def runtime_hint(detail: str) -> str:
    return (
        f"{detail}. Project runtime should be "
        f"JupyterLab / Python 3.13 / {CUSTOM_RUNTIME_EDITION} "
        f"(register from the repository root Dockerfile)."
    )
