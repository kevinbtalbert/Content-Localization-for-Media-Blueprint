#!/usr/bin/env python3
"""AMP session: build the Next.js demo application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.paths import PROJECT_ROOT  # noqa: E402

DEMO_DIR = PROJECT_ROOT / "client" / "demos"


def main() -> int:
    os.chdir(DEMO_DIR)
    env = {**os.environ, "NEXT_PUBLIC_INPUT_FILE_NAME": os.environ.get("DEFAULT_INPUT_FILE_NAME", "sample_video.mp4")}
    for cmd in (
        ["npm", "ci"],
        ["npm", "run", "generate-ts-protos"],
        ["npm", "run", "build"],
    ):
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True, env=env)
    print("✅ Demo UI built")
    return 0


run_amp_entry(main, __name__)
