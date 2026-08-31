#!/usr/bin/env python3
"""AMP session: record NIM image refs (platform pulls images; no Docker socket)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.nim_runtime import (  # noqa: E402
    nim_bundle_ready,
    validate_ngc_for_nim,
    write_nim_image_manifest,
)
from cai.lib.paths import ensure_cai_dirs  # noqa: E402


def main() -> int:
    ensure_cai_dirs()
    validate_ngc_for_nim()
    manifest_path = write_nim_image_manifest()
    if not nim_bundle_ready("lipsync") or not nim_bundle_ready("asd"):
        print("❌ NIM bundles missing from runtime image — rebuild ContentLocalization v1.2")
        return 1
    print("✅ NGC_API_KEY present")
    print("✅ Bundled NIM metadata written (LipSync + ASD in ContentLocalization image)")
    print(f"   {manifest_path}")
    return 0


run_amp_entry(main, __name__)
