"""Helpers for CAI AMP session and application entry points."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable


def bootstrap_sys_path() -> Path:
    """Put the project root on sys.path (safe when __file__ is undefined)."""
    root = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def should_run_amp_entry(module_name: str) -> bool:
    """True when invoked as a script or from a CAI/Jupyter run_session kernel."""
    if module_name == "__main__":
        return True
    try:
        get_ipython  # type: ignore[name-defined]  # noqa: F821
    except NameError:
        return False
    return True


def run_amp_entry(main_func: Callable[[], int], module_name: str) -> None:
    """Call main() for CLI and CAI AMP session execution."""
    if should_run_amp_entry(module_name):
        raise SystemExit(main_func())
