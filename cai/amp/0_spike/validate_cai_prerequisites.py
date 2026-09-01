#!/usr/bin/env python3
"""Phase-0 spike: validate CAI cluster prerequisites before full AMP install."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# CAI run_session kernels do not define __file__; use CDSW_PROJECT_DIR instead.
sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.gpu_config import detect_gpu_profile, save_gpu_profile  # noqa: E402
from cai.lib.nim_runtime import (  # noqa: E402
    NIM_BUNDLE_ROOT,
    nim_bundle_ready,
    write_nim_image_manifest,
)
from cai.lib.paths import PROJECT_ROOT, RAY_ROOT  # noqa: E402
from cai.lib.prerequisite_checks import (  # noqa: E402
    CUSTOM_RUNTIME_EDITION,
    find_tool,
    get_elevenlabs_api_key,
    get_ngc_api_key,
    runtime_hint,
)


def check(label: str, ok: bool, detail: str = "", *, required: bool = True) -> bool:
    status = "WARN" if not ok and not required else ("PASS" if ok else "FAIL")
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))
    if ok:
        return True
    return not required


def main() -> int:
    print("=" * 70)
    print("CAI prerequisite validation (Phase 0 spike)")
    print("=" * 70)
    print(f"Expected runtime edition: {CUSTOM_RUNTIME_EDITION}")
    print(f"ML_RUNTIME_EDITION: {os.environ.get('ML_RUNTIME_EDITION', '(not set)')}")
    print("Deployment model: bundled NIM GPU apps (ContentLocalization runtime)")
    print()

    results: list[bool] = []

    results.append(check("Project root exists", PROJECT_ROOT.exists(), str(PROJECT_ROOT)))
    results.append(check("Ray integration present", (RAY_ROOT / "cai_integration").exists()))

    ngc_key = get_ngc_api_key()
    results.append(
        check(
            "NGC_API_KEY set",
            bool(ngc_key),
            f"{len(ngc_key)} chars" if ngc_key else "os.environ.get('NGC_API_KEY') is empty",
        )
    )

    s2s_service = os.environ.get("S2S_SERVICE", "EL_DUBBING")
    if s2s_service == "EL_DUBBING":
        eleven_key = get_elevenlabs_api_key()
        results.append(
            check(
                "ELEVENLABS_API_KEY set",
                bool(eleven_key),
                f"{len(eleven_key)} chars" if eleven_key else "os.environ.get('ELEVENLABS_API_KEY') is empty",
                required=False,
            )
        )

    node = find_tool("node")
    node_ver = ""
    if node:
        node_ver = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    results.append(
        check(
            "node available",
            node is not None,
            runtime_hint(node_ver or "not found"),
        )
    )

    grpcurl = find_tool("grpcurl")
    results.append(
        check(
            "grpcurl available",
            grpcurl is not None,
            runtime_hint(grpcurl or "not found"),
        )
    )

    gpu_proc = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True)
    gpu_visible = gpu_proc.returncode == 0
    results.append(check("NVIDIA GPU visible", gpu_visible, gpu_proc.stdout.strip()[:120]))

    gpu_profile = detect_gpu_profile() if gpu_visible else None
    if gpu_profile:
        profile_path = save_gpu_profile(gpu_profile)
        results.append(
            check(
                "GPU profile detected",
                True,
                f"{gpu_profile.accelerator_type} -> {profile_path}",
            )
        )
        report_gpu = gpu_profile.gpu_name
    else:
        results.append(
            check(
                "GPU profile detected",
                False,
                "nvidia-smi gpu_name required for GPU NIM application placement",
            )
        )
        report_gpu = gpu_proc.stdout.strip() if gpu_visible else gpu_proc.stderr.strip()

    if ngc_key:
        manifest_path = write_nim_image_manifest()
        results.append(
            check(
                "NIM image manifest",
                manifest_path.exists(),
                str(manifest_path),
            )
        )
        results.append(
            check(
                "LipSync NIM bundle in runtime image",
                nim_bundle_ready("lipsync"),
                str(NIM_BUNDLE_ROOT / "lipsync"),
            )
        )
        results.append(
            check(
                "ASD NIM bundle in runtime image",
                nim_bundle_ready("asd"),
                str(NIM_BUNDLE_ROOT / "asd"),
            )
        )

    report = {
        "project_root": str(PROJECT_ROOT),
        "runtime_edition": os.environ.get("ML_RUNTIME_EDITION"),
        "expected_runtime_edition": CUSTOM_RUNTIME_EDITION,
        "deployment_model": "bundled_nim_in_contentlocalization_runtime",
        "docker_socket_required": False,
        "node": node_ver,
        "grpcurl": grpcurl,
        "ngc_key_set": bool(ngc_key),
        "s2s_service": s2s_service,
        "elevenlabs_key_set": bool(get_elevenlabs_api_key()) if s2s_service == "EL_DUBBING" else None,
        "gpu": report_gpu,
        "gpu_profile": gpu_profile.to_dict() if gpu_profile else None,
    }
    report_path = PROJECT_ROOT / "cai" / "config" / "phase0_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nReport written to {report_path}")

    if all(results):
        print("\nAll prerequisite checks passed.")
        return 0

    print("\nOne or more checks failed. Review output before continuing the AMP install.")
    if os.environ.get("ML_RUNTIME_EDITION") != CUSTOM_RUNTIME_EDITION:
        print(
            f"\nTip: set the project runtime to '{CUSTOM_RUNTIME_EDITION}' "
            "(built from the repository root Dockerfile and registered in Runtime Catalog)."
        )
    if not ngc_key:
        print(
            "\nTip: set NGC_API_KEY under Project Settings → Advanced → Environment, "
            "click Submit, then start a new session."
        )
    return 1


run_amp_entry(main, __name__)
