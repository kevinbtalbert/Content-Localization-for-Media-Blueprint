"""Shared helpers for CAI AMP prerequisite validation."""

from __future__ import annotations

import json
import os
import re
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


# Placeholders written when AMP/CAI UI stringifies metadata objects instead of secrets.
_INVALID_ENV_SECRET_RE = re.compile(
    r"^\[object\s+object\]$|^\[object\s+Object\]$",
    re.IGNORECASE,
)
_INVALID_ENV_SECRET_LITERALS = frozenset(
    {
        "",
        "enter value",
        "null",
        "undefined",
        "none",
    }
)


def is_invalid_env_secret(value: str) -> bool:
    """True when a value is empty or a known AMP/CAI placeholder, not a real secret."""
    normalized = value.strip()
    if normalized.casefold() in _INVALID_ENV_SECRET_LITERALS:
        return True
    if _INVALID_ENV_SECRET_RE.match(normalized):
        return True
    if normalized.startswith("{") and normalized.endswith("}"):
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            return False
        if isinstance(parsed, dict) and {"default", "description"} & set(parsed):
            return True
    return False


def resolve_env_secret(*keys: str) -> str:
    """Return the first usable secret from os.environ for the given variable names."""
    for key in keys:
        raw = os.environ.get(key)
        if raw is None:
            continue
        value = raw.strip()
        if value and not is_invalid_env_secret(value):
            return value
    return ""


def describe_env_secret(*keys: str) -> str:
    """Human-readable status for prerequisite output (never prints secret values)."""
    parts: list[str] = []
    for key in keys:
        raw = os.environ.get(key)
        if raw is None:
            parts.append(f"{key} not in session environment")
            continue
        value = raw.strip()
        if not value:
            parts.append(f"{key} is empty")
        elif is_invalid_env_secret(value):
            if value.casefold() == "[object object]":
                parts.append(
                    f"{key}=[object Object] (AMP UI saved metadata instead of your key — "
                    "delete the row, re-add the variable with the plain key string, Submit, "
                    "then start a new session)"
                )
            else:
                parts.append(f"{key} has invalid placeholder value")
        else:
            parts.append(f"{key} set ({len(value)} chars)")
    return "; ".join(parts) if parts else "not set"


def get_ngc_api_key() -> str:
    """Return NGC credentials from project environment (several aliases supported)."""
    return resolve_env_secret("NGC_API_KEY", "LIPSYNC_API_KEY", "ASD_API_KEY")


def get_elevenlabs_api_key() -> str:
    """Return ElevenLabs API key from project environment."""
    return resolve_env_secret("ELEVENLABS_API_KEY")


def runtime_hint(detail: str) -> str:
    return (
        f"{detail}. Project runtime should be "
        f"JupyterLab / Python 3.13 / {CUSTOM_RUNTIME_EDITION} "
        f"(register from the repository root Dockerfile)."
    )
