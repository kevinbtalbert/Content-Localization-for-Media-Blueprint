#!/usr/bin/env python3
"""Verify NGC_API_KEY can authenticate and pull LipSync/ASD NIM images."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.deploy_mode import deploy_mode_label, is_serverless_nim_mode  # noqa: E402
from cai.lib.ngc_auth import resolve_ngc_bearer_token, verify_nim_model_access  # noqa: E402


def main() -> int:
    print("=" * 70)
    print("NGC access verification for Content Localization NIMs")
    print("=" * 70)
    print(f"Deployment model: {deploy_mode_label()}")
    print()

    raw = os.environ.get("NGC_API_KEY", "").strip()
    if not raw:
        print("[FAIL] NGC_API_KEY is not set in project environment.")
        return 1

    print(f"[INFO] NGC_API_KEY length: {len(raw)} characters")
    print(
        "[INFO] Use an API key from https://org.ngc.nvidia.com/setup/api-key "
        "(not a pasted CLI config blob unless it is base64 client_id:secret)."
    )
    print()

    try:
        auth = resolve_ngc_bearer_token(raw)
        print(f"[PASS] NGC authentication ({auth.method})")
        print(f"       {auth.detail}")
    except RuntimeError as exc:
        print(f"[FAIL] NGC authentication: {exc}")
        print()
        print("Fix:")
        print("  1. Create a fresh API key in NGC → Setup → Generate API Key")
        print("  2. Set NGC_API_KEY in Project Settings → Environment")
        print("  3. Re-run this step before starting LipSync/ASD applications")
        return 1

    print()
    if is_serverless_nim_mode():
        print("Serverless mode: NGC authentication is sufficient (skipping nvcr.io NIM image pulls).")
        return 0

    failures = 0
    for label, ok, detail in verify_nim_model_access():
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {label}: {detail}")
        if not ok:
            failures += 1

    if failures:
        print()
        print(
            "LipSync requires NVIDIA AI for Media private access: "
            "https://developer.nvidia.com/ai-for-media/private-access-program"
        )
        return 1

    print()
    print("NGC access looks good. LipSync/ASD NIM apps should be able to download models.")
    return 0


run_amp_entry(main, __name__)
