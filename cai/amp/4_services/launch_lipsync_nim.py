#!/usr/bin/env python3
"""CAI application entry: LipSync NIM (exec bash launcher — keeps NIM in foreground)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.deploy_mode import is_serverless_nim_mode  # noqa: E402
from cai.lib.launch_app import exec_bash_script, exec_serverless_nim_placeholder  # noqa: E402

if is_serverless_nim_mode():
    exec_serverless_nim_placeholder("lipsync-nim-serverless")
else:
    exec_bash_script("cai/amp/4_services/launch_lipsync_nim.sh")
