#!/usr/bin/env python3
"""AMP session: NGC login and pre-pull NIM container images."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.paths import ensure_cai_dirs  # noqa: E402
from cai.lib.prerequisite_checks import get_ngc_api_key  # noqa: E402

LIPSYNC_IMAGE = os.environ.get("LIPSYNC_IMAGE", "nvcr.io/nim/nvidia/lipsync:1.3.0")
ASD_IMAGE = os.environ.get("ASD_IMAGE", "nvcr.io/nim/nvidia/active-speaker-detection:1.1.0")


def main() -> int:
    ensure_cai_dirs()
    api_key = get_ngc_api_key()
    if not api_key:
        print("❌ NGC_API_KEY is required (Project Settings → Advanced → Environment)")
        return 1

    tags = os.environ.get("LIPSYNC_NIM_TAGS_SELECTOR", "language=de")
    if tags and "language=" in tags:
        os.environ.setdefault("LIPSYNC_NIM_TAGS_SELECTOR", tags)

    print("Logging in to nvcr.io...")
    subprocess.run(
        ["docker", "login", "nvcr.io", "-u", "$oauthtoken", "-p", api_key],
        check=True,
    )

    for image in (LIPSYNC_IMAGE, ASD_IMAGE):
        print(f"Pulling {image}...")
        subprocess.run(["docker", "pull", image], check=True)

    print("✅ NIM images pulled")
    return 0


run_amp_entry(main, __name__)
