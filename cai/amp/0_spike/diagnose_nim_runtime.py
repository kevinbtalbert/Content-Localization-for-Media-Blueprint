#!/usr/bin/env python3
"""Collect NIM runtime diagnostics for LipSync/ASD debugging on CAI.

Run in a Workbench session (Python 3.13, ContentLocalization runtime):

  python3 cai/amp/0_spike/diagnose_nim_runtime.py

Paste the JSON block at the end into chat for follow-up debugging.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.nim_runtime import NIM_BUNDLE_ROOT, nim_bundle_ready  # noqa: E402
from cai.lib.paths import NIM_ENDPOINTS_JSON, PROJECT_ROOT  # noqa: E402

REPORT_VERSION = "1.0"
NIM_TYPES = ("lipsync", "asd")
DEFAULT_PORTS = {"lipsync": 8004, "asd": 8005}
LOG_PATHS = {
    "lipsync": (
        PROJECT_ROOT / "cai/config/lipsync_nim.log",
        PROJECT_ROOT / "cai/config/lipsync_sidecar.log",
    ),
    "asd": (
        PROJECT_ROOT / "cai/config/asd_nim.log",
        PROJECT_ROOT / "cai/config/asd_sidecar.log",
    ),
}


def _run(cmd: list[str], *, timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": " ".join(cmd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"cmd": " ".join(cmd), "error": str(exc)}


def _dir_size(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "exists": False}
    du = _run(["du", "-sh", str(path)])
    line = du.get("stdout", "")
    size = line.split()[0] if line else "?"
    return {"path": str(path), "exists": True, "size": size}


def _read_tail(path: Path, lines: int = 40) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    try:
        content = path.read_text(errors="replace").splitlines()
        return {
            "path": str(path),
            "exists": True,
            "line_count": len(content),
            "tail": content[-lines:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"path": str(path), "exists": True, "error": str(exc)}


def _probe_http(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(512).decode(errors="replace")
            return {"url": url, "ok": resp.status == 200, "status": resp.status, "body_preview": body[:200]}
    except urllib.error.HTTPError as exc:
        return {"url": url, "ok": False, "status": exc.code, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "ok": False, "error": str(exc)}


def _parse_shm_from_log(tail: list[str]) -> str | None:
    for line in reversed(tail):
        if "/dev/shm:" in line:
            return line.strip()
    return None


def _grep_log_file(path: Path, pattern: str, *, max_lines: int = 30) -> list[str]:
    if not path.is_file():
        return []
    try:
        rx = re.compile(pattern, re.I)
        return [line for line in path.read_text(errors="replace").splitlines() if rx.search(line)][-max_lines:]
    except Exception:  # noqa: BLE001
        return []


def _read_head(path: Path, lines: int = 80) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    try:
        content = path.read_text(errors="replace").splitlines()
        return {
            "path": str(path),
            "exists": True,
            "line_count": len(content),
            "head": content[:lines],
        }
    except Exception as exc:  # noqa: BLE001
        return {"path": str(path), "exists": True, "error": str(exc)}


def _grep_log_patterns(tail: list[str]) -> dict[str, list[str]]:
    patterns = {
        "shm": re.compile(r"/dev/shm", re.I),
        "triton": re.compile(r"Triton Inference Server", re.I),
        "health_ready": re.compile(r"health/ready|NIM ready", re.I),
        "not_ready": re.compile(r"not ready yet|no listener", re.I),
        "gpu_uuid": re.compile(r"NVIDIA_VISIBLE_DEVICES|GPU-", re.I),
        "seeded": re.compile(r"seeded|Seeding", re.I),
        "error": re.compile(r"\b(ERROR|Error|exit code|failed)\b"),
    }
    hits: dict[str, list[str]] = {key: [] for key in patterns}
    for line in tail:
        for key, pat in patterns.items():
            if pat.search(line):
                hits[key].append(line.strip())
    return hits


def _list_applications() -> dict[str, Any]:
    key = os.environ.get("CDSW_APIV2_KEY") or os.environ.get("CML_API_KEY")
    project_id = os.environ.get("CDSW_PROJECT_ID") or os.environ.get("CML_PROJECT_ID")
    domain = os.environ.get("CDSW_DOMAIN", "").strip()
    if not key or not project_id or not domain:
        return {
            "available": False,
            "reason": "Need CDSW_APIV2_KEY, CDSW_PROJECT_ID, CDSW_DOMAIN in session env",
        }
    url = f"https://{domain}/api/v2/projects/{project_id}/applications?page_size=100"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        apps = []
        for item in data.get("applications", []):
            apps.append(
                {
                    "name": item.get("name"),
                    "status": item.get("status"),
                    "subdomain": item.get("subdomain"),
                    "cpu": item.get("cpu"),
                    "memory": item.get("memory"),
                    "nvidia_gpu": item.get("nvidia_gpu"),
                    "runtime_identifier": item.get("runtime_identifier"),
                }
            )
        return {"available": True, "applications": apps}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}


def _project_shared_memory() -> dict[str, Any]:
    key = os.environ.get("CDSW_APIV2_KEY") or os.environ.get("CML_API_KEY")
    project_id = os.environ.get("CDSW_PROJECT_ID") or os.environ.get("CML_PROJECT_ID")
    domain = os.environ.get("CDSW_DOMAIN", "").strip()
    if not key or not project_id or not domain:
        return {"available": False}
    url = f"https://{domain}/api/v2/projects/{project_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return {
            "available": True,
            "shared_memory_limit_mb": data.get("shared_memory_limit"),
            "name": data.get("name"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}


def _nim_endpoints() -> dict[str, Any]:
    if not NIM_ENDPOINTS_JSON.is_file():
        return {"exists": False, "path": str(NIM_ENDPOINTS_JSON)}
    try:
        data = json.loads(NIM_ENDPOINTS_JSON.read_text())
        return {"exists": True, "path": str(NIM_ENDPOINTS_JSON), "data": data}
    except Exception as exc:  # noqa: BLE001
        return {"exists": True, "path": str(NIM_ENDPOINTS_JSON), "error": str(exc)}


def _remote_health(endpoints: dict[str, Any]) -> dict[str, Any]:
    """Probe NIM health via pod IP from nim_endpoints.json (session cannot use 127.0.0.1:8004)."""
    results: dict[str, Any] = {}
    if not endpoints.get("exists") or "data" not in endpoints:
        return {"note": "nim_endpoints.json missing — NIM never published ready endpoint", "probes": results}

    for nim_type, port in DEFAULT_PORTS.items():
        entry = endpoints["data"].get(nim_type) or {}
        host = entry.get("pod_ip") or entry.get("host") or entry.get("ip")
        http_port = entry.get("http_port") or port
        if not host:
            results[nim_type] = {"skipped": True, "reason": "no pod_ip in nim_endpoints.json"}
            continue
        url = f"http://{host}:{http_port}/v1/health/ready"
        results[nim_type] = _probe_http(url)
    return {"probes": results}


def main() -> int:
    report: dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "session": {
            "hostname": socket.gethostname(),
            "pod_ip": os.environ.get("CDSW_IP_ADDRESS"),
            "engine_type": os.environ.get("CDSW_ENGINE_TYPE"),
            "project_dir": str(PROJECT_ROOT),
            "runtime_edition": os.environ.get("ML_RUNTIME_EDITION"),
            "runtime_version": os.environ.get("ML_RUNTIME_SHORT_VERSION"),
            "ngc_key_set": bool(os.environ.get("NGC_API_KEY", "").strip()),
            "nvidia_visible_devices": os.environ.get("NVIDIA_VISIBLE_DEVICES"),
        },
    }

    print("=" * 70)
    print("NIM runtime diagnostics (paste JSON block at end into chat)")
    print("=" * 70)
    print()
    print("NOTE: This session's /dev/shm may differ from GPU application pods.")
    print("      Check lipsync_nim.log for '/dev/shm:' inside the LipSync app.")
    print()

    # Session-level checks
    shm = _run(["df", "-h", "/dev/shm"])
    report["session_shm"] = shm
    print("[session] /dev/shm")
    print(shm.get("stdout") or shm.get("error") or shm.get("stderr") or "(no output)")
    print()

    gpu = _run(["nvidia-smi", "-L"])
    report["session_gpu"] = gpu
    print("[session] nvidia-smi -L")
    print(gpu.get("stdout") or gpu.get("stderr") or "(not available in this session)")
    print()

    report["project_shared_memory"] = _project_shared_memory()
    if report["project_shared_memory"].get("available"):
        mb = report["project_shared_memory"].get("shared_memory_limit_mb")
        print(f"[project] shared_memory_limit = {mb} MB")
    else:
        print("[project] shared_memory_limit — could not read via API (need CDSW_APIV2_KEY)")
    print()

    report["applications"] = _list_applications()
    if report["applications"].get("available"):
        print("[applications]")
        for app in report["applications"].get("applications", []):
            print(
                f"  - {app.get('name')}: status={app.get('status')} "
                f"gpu={app.get('nvidia_gpu')} mem={app.get('memory')}GB"
            )
    print()

    # Bundles and caches
    report["bundles"] = {}
    report["caches"] = {}
    for nim in NIM_TYPES:
        bundle = NIM_BUNDLE_ROOT / nim
        baked = Path(f"/opt/nvidia-nim/baked-model-cache/{nim}")
        volume = PROJECT_ROOT / "volumes" / "models" / nim
        report["bundles"][nim] = {
            "ready": nim_bundle_ready(nim),
            "bundle_root": _dir_size(bundle),
            "baked_cache": _dir_size(baked),
        }
        report["caches"][nim] = _dir_size(volume)

        print(f"[{nim}] bundle ready={report['bundles'][nim]['ready']}")
        print(f"  baked:  {report['bundles'][nim]['baked_cache']}")
        print(f"  volume: {report['caches'][nim]}")
    print()

    # NIM env files written by app launchers
    report["nim_env_files"] = {}
    for nim in NIM_TYPES:
        env_path = PROJECT_ROOT / "cai" / "config" / f"{nim}_nim.env"
        if env_path.is_file():
            text = env_path.read_text(errors="replace")
            report["nim_env_files"][nim] = {
                "path": str(env_path),
                "ngc_key_set": "NGC_API_KEY=" in text and 'NGC_API_KEY=""' not in text,
                "lines": len(text.splitlines()),
            }
        else:
            report["nim_env_files"][nim] = {"path": str(env_path), "exists": False}
    print("[nim env files]")
    for nim, info in report["nim_env_files"].items():
        print(f"  {nim}: {info}")
    print()

    # Logs
    report["logs"] = {}
    for nim in NIM_TYPES:
        nim_log, sidecar_log = LOG_PATHS[nim]
        nim_tail = _read_tail(nim_log, 60)
        nim_head = _read_head(nim_log, 80)
        side_tail = _read_tail(sidecar_log, 40)
        all_nim_lines = []
        if nim_log.is_file():
            all_nim_lines = nim_log.read_text(errors="replace").splitlines()
        report["logs"][nim] = {
            "nim_log_head": nim_head,
            "nim_log_tail": nim_tail,
            "sidecar_log": side_tail,
            "shm_from_app_log": _parse_shm_from_log(all_nim_lines),
            "startup_grep": {
                "triton": _grep_log_file(nim_log, r"Triton Inference Server"),
                "gpu_uuid": _grep_log_file(nim_log, r"NVIDIA_VISIBLE_DEVICES|Adjusted NVIDIA"),
                "seeded": _grep_log_file(nim_log, r"seeded|Seeding"),
                "shm": _grep_log_file(nim_log, r"/dev/shm"),
                "errors": _grep_log_file(nim_log, r"ERROR|failed|exit code"),
            },
            "patterns": _grep_log_patterns(nim_tail.get("tail", []) + side_tail.get("tail", [])),
        }
        print(f"[{nim}] log analysis (startup from full log, not just tail)")
        sg = report["logs"][nim]["startup_grep"]
        for key in ("shm", "triton", "gpu_uuid", "seeded", "errors"):
            hits = sg.get(key, [])
            if hits:
                print(f"  {key}: {hits[-1][:140]}")
            else:
                print(f"  {key}: (not found — app may need restart)")
    print()

    report["nim_endpoints"] = _nim_endpoints()
    report["remote_health"] = _remote_health(report["nim_endpoints"])
    print("[health probes via pod IP]")
    for nim, probe in report["remote_health"].get("probes", {}).items():
        print(f"  {nim}: {probe}")
    print()

    # Localhost probes (only meaningful if run inside the NIM app itself)
    report["localhost_health"] = {
        nim: _probe_http(f"http://127.0.0.1:{port}/v1/health/ready")
        for nim, port in DEFAULT_PORTS.items()
    }
    print("[localhost health — usually fails in Workbench session, OK to ignore]")
    for nim, probe in report["localhost_health"].items():
        print(f"  {nim} :{DEFAULT_PORTS[nim]} -> ok={probe.get('ok')} {probe.get('error', probe.get('status', ''))}")
    print()

    report["git_head"] = _run(["git", "-C", str(PROJECT_ROOT), "log", "-1", "--oneline"])
    launcher = PROJECT_ROOT / "cai/runtime/scripts/run-bundled-nim.sh"
    report["launcher"] = {
        "path": str(launcher),
        "exists": launcher.is_file(),
        "has_shm_failfast": False,
    }
    if launcher.is_file():
        text = launcher.read_text(errors="replace")
        report["launcher"]["has_shm_failfast"] = "ERROR: /dev/shm is only" in text

    print("[repo]")
    print(f"  HEAD: {report['git_head'].get('stdout', '?')}")
    print(f"  run-bundled-nim.sh fail-fast shm check: {report['launcher']['has_shm_failfast']}")
    print()

    print("=" * 70)
    print("JSON REPORT (copy everything between the markers)")
    print("=" * 70)
    print("---BEGIN NIM DIAG JSON---")
    print(json.dumps(report, indent=2, default=str))
    print("---END NIM DIAG JSON---")

    return 0


if __name__ == "__main__":
    raise SystemExit(run_amp_entry(main, __name__))
