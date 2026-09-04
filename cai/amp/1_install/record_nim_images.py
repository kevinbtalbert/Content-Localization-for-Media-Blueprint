#!/usr/bin/env python3
"""AMP session: record NIM image refs (platform pulls images; no Docker socket)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.deploy_mode import is_serverless_nim_mode, skip_message  # noqa: E402
from cai.lib.ngc_auth import verify_nim_model_access  # noqa: E402
from cai.lib.nim_runtime import (  # noqa: E402
    nim_bundle_ready,
    validate_ngc_for_nim,
    write_nim_image_manifest,
)
from cai.lib.paths import ensure_cai_dirs  # noqa: E402


def main() -> int:
    if is_serverless_nim_mode():
        print(skip_message("Record NIM Bundle Configuration"))
        return 0

    ensure_cai_dirs()
    validate_ngc_for_nim()
    manifest_path = write_nim_image_manifest()
    if not nim_bundle_ready("lipsync") or not nim_bundle_ready("asd"):
        print("❌ NIM bundles missing from runtime image — rebuild ContentLocalization v1.5")
        return 1

    failures = 0
    for label, ok, detail in verify_nim_model_access():
        mark = "✅" if ok else "❌"
        print(f"{mark} {label}: {detail}")
        if not ok:
            failures += 1

    print(f"   {manifest_path}")
    if failures:
        print("Run cai/amp/0_spike/verify_ngc_access.py for full NGC diagnostics.")
        return 1
    print("✅ NGC auth and nvcr.io pull access verified for LipSync + ASD NIM images")
    return 0


run_amp_entry(main, __name__)
