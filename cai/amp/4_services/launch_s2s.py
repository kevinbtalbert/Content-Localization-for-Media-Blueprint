#!/usr/bin/env python3
"""CAI application entry: Speech-to-Speech service."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.launch_app import run_bash_script  # noqa: E402


def main() -> int:
    return run_bash_script("cai/amp/4_services/launch_s2s.sh")


run_amp_entry(main, __name__)
