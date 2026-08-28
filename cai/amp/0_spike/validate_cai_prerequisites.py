#!/usr/bin/env python3
"""Phase-0 spike: validate CAI cluster prerequisites before full AMP install."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# CAI run_session kernels do not define __file__; use CDSW_PROJECT_DIR instead.
sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.gpu_config import detect_gpu_profile, save_gpu_profile  # noqa: E402
from cai.lib.paths import PROJECT_ROOT, RAY_ROOT  # noqa: E402


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    print("=" * 70)
    print("CAI prerequisite validation (Phase 0 spike)")
    print("=" * 70)

    results: list[bool] = []

    results.append(check("Project root exists", PROJECT_ROOT.exists(), str(PROJECT_ROOT)))
    results.append(check("Ray integration present", (RAY_ROOT / "cai_integration").exists()))

    docker = shutil.which("docker")
    results.append(check("docker CLI available", docker is not None, docker or "not found"))
    if docker:
        proc = subprocess.run([docker, "info"], capture_output=True, text=True)
        results.append(check("docker daemon reachable", proc.returncode == 0, proc.stderr.strip()[:120]))

    ngc_key = os.environ.get("NGC_API_KEY", "")
    results.append(check("NGC_API_KEY set", bool(ngc_key), "required for NIM image pull"))

    node = shutil.which("node")
    node_ver = ""
    if node:
        node_ver = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    results.append(check("node available", node is not None, node_ver or "not found"))

    grpcurl = shutil.which("grpcurl")
    results.append(check("grpcurl available", grpcurl is not None, grpcurl or "install via custom runtime"))

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
                "nvidia-smi gpu_name required for Ray worker placement",
            )
        )
        report_gpu = gpu_proc.stdout.strip() if gpu_visible else gpu_proc.stderr.strip()

    report = {
        "project_root": str(PROJECT_ROOT),
        "docker": docker,
        "node": node_ver,
        "grpcurl": grpcurl,
        "ngc_key_set": bool(ngc_key),
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
    print("\nOne or more checks failed. Review output before AMP install.")
    return 1


run_amp_entry(main, __name__)
