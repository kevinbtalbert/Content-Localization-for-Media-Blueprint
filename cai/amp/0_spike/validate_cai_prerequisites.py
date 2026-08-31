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
from cai.lib.paths import PROJECT_ROOT, RAY_ROOT  # noqa: E402
from cai.lib.prerequisite_checks import (  # noqa: E402
    CUSTOM_RUNTIME_EDITION,
    find_tool,
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
    print()

    results: list[bool] = []

    results.append(check("Project root exists", PROJECT_ROOT.exists(), str(PROJECT_ROOT)))
    results.append(check("Ray integration present", (RAY_ROOT / "cai_integration").exists()))

    docker = find_tool("docker")
    results.append(
        check(
            "docker CLI available",
            docker is not None,
            runtime_hint(docker or "not found"),
        )
    )
    docker_daemon_ok = False
    if docker:
        proc = subprocess.run([docker, "info"], capture_output=True, text=True)
        docker_daemon_ok = proc.returncode == 0
        detail = proc.stderr.strip()[:160] if not docker_daemon_ok else "ok"
        if not docker_daemon_ok:
            detail = (
                f"{detail} — sessions often lack /var/run/docker.sock; "
                "required for Pull NIM Images and Ray GPU workers (ask admin to enable)"
            )
        results.append(
            check(
                "docker daemon reachable",
                docker_daemon_ok,
                detail,
                required=False,
            )
        )

    ngc_key = get_ngc_api_key()
    results.append(
        check(
            "NGC_API_KEY set",
            bool(ngc_key),
            "set in AMP Configure Project or Project Settings → Advanced → Environment "
            "(required before Pull NIM Images)",
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
                "nvidia-smi gpu_name required for Ray worker placement",
            )
        )
        report_gpu = gpu_proc.stdout.strip() if gpu_visible else gpu_proc.stderr.strip()

    report = {
        "project_root": str(PROJECT_ROOT),
        "runtime_edition": os.environ.get("ML_RUNTIME_EDITION"),
        "expected_runtime_edition": CUSTOM_RUNTIME_EDITION,
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
        if not ngc_key or (docker and not docker_daemon_ok):
            print("\nPrerequisite checks passed with warnings.")
            if not ngc_key:
                print(
                    "  • Add NGC_API_KEY before the Pull NIM Images AMP step "
                    "(Project Settings → Advanced → Environment)."
                )
            if docker and not docker_daemon_ok:
                print(
                    "  • Docker socket not available in this session — confirm your admin "
                    "allows /var/run/docker.sock on GPU sessions/workers for NIM pull."
                )
        else:
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
            "\nTip: add NGC_API_KEY under Project Settings → Advanced → Environment, "
            "then re-run this session."
        )
    return 1


run_amp_entry(main, __name__)
