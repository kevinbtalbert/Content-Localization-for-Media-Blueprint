#!/usr/bin/env python3
"""CAI application entry: ASD NIM."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.deploy_mode import is_serverless_nim_mode  # noqa: E402
from cai.lib.launch_app import run_bash_script, run_serverless_nim_placeholder  # noqa: E402


def main() -> int:
    if is_serverless_nim_mode():
        return run_serverless_nim_placeholder("asd-nim-serverless")
    return run_bash_script("cai/amp/4_services/launch_asd_nim.sh")


run_amp_entry(main, __name__)
