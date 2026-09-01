#!/usr/bin/env python3
"""Deprecated: CAI has no Docker socket. Delegates to record_nim_images.py."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_PROJECT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(_PROJECT))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402

_record_path = Path(__file__).with_name("record_nim_images.py")
_spec = importlib.util.spec_from_file_location("record_nim_images", _record_path)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)
main = _module.main

if __name__ == "__main__":
    print("Note: docker pull is not used on CAI (no Docker socket). Recording image config instead.")
    run_amp_entry(main, "__main__")
