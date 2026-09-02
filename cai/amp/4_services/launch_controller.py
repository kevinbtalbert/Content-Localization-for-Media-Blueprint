#!/usr/bin/env python3
"""CAI application entry: Controller service."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.launch_app import exec_bash_script  # noqa: E402

exec_bash_script("cai/amp/4_services/launch_controller.sh")
