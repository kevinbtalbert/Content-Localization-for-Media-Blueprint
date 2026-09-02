#!/usr/bin/env python3
"""
Validate cross-application connectivity to LipSync NIM on Cloudera AI.

Run from a session or another application pod (S2S, Controller). Uses cmlapi
for dynamic app discovery and cai/nim_endpoints.json for AMP-style pod IP wiring.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.deploy_mode import (  # noqa: E402
    deploy_mode_label,
    is_serverless_nim_mode,
    serverless_grpc_address,
    validate_serverless_config,
)
from cai.lib.paths import NIM_ENDPOINTS_JSON  # noqa: E402

DEFAULT_LIPSYNC_NAME = "LipSync NIM"
DEFAULT_LIPSYNC_SUBDOMAIN = "cl-lipsync"
DEFAULT_LIPSYNC_HTTP_PORT = 8004
DEFAULT_LIPSYNC_GRPC_PORT = 50054

IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$"
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _as_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    out: dict[str, Any] = {}
    for key in dir(obj):
        if key.startswith("_"):
            continue
        try:
            val = getattr(obj, key)
        except Exception:
            continue
        if callable(val):
            continue
        out[key] = val
    return out


def _cml_host() -> str:
    host = (os.environ.get("CML_HOST") or "").strip()
    if host:
        return host.rstrip("/")
    domain = (os.environ.get("CDSW_DOMAIN") or "").strip()
    if domain:
        return f"https://{domain}"
    project_url = (os.environ.get("CDSW_PROJECT_URL") or "").strip().rstrip("/")
    if project_url and "/api/v2/" in project_url:
        return project_url.split("/api/v2/")[0]
    raise RuntimeError("Set CML_HOST or CDSW_DOMAIN (or CDSW_PROJECT_URL)")


def _project_id() -> str:
    pid = os.environ.get("CDSW_PROJECT_ID") or os.environ.get("CML_PROJECT_ID")
    if not pid:
        raise RuntimeError("CDSW_PROJECT_ID / CML_PROJECT_ID not set")
    return pid


def _make_cml_client() -> Any:
    import cmlapi

    try:
        return cmlapi.default_client()
    except TypeError:
        api_key = os.environ.get("CDSW_APIV2_KEY") or os.environ.get("CML_API_KEY")
        if not api_key:
            raise RuntimeError("CDSW_APIV2_KEY / CML_API_KEY not set") from None
        return cmlapi.default_client(url=_cml_host(), cml_api_key=api_key)


def _list_applications(client: Any, project_id: str) -> list[dict[str, Any]]:
    apps: list[dict[str, Any]] = []
    page_token = ""
    while True:
        kwargs: dict[str, Any] = {"project_id": project_id, "page_size": 100}
        if page_token:
            kwargs["page_token"] = page_token
        resp = client.list_applications(**kwargs)
        batch = getattr(resp, "applications", None) or []
        apps.extend(_as_dict(a) for a in batch)
        page_token = getattr(resp, "next_page_token", "") or ""
        if not page_token:
            break
    return apps


def _find_lipsync_app(apps: list[dict[str, Any]], *, name: str, subdomain: str) -> dict[str, Any] | None:
    for app in apps:
        if app.get("name") == name:
            return app
        sub = str(app.get("subdomain", ""))
        if sub == subdomain or sub.startswith(f"{subdomain}-"):
            return app
    for app in apps:
        blob = json.dumps(app).lower()
        if "lipsync" in blob:
            return app
    return None


def _http_probe(url: str, *, timeout: float = 10.0) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(4096).decode(errors="replace")
            return resp.status, body[:500]
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(4096).decode(errors="replace")
        except Exception:
            body = str(exc)
        return exc.code, body[:500]
    except Exception as exc:
        return None, str(exc)


def _tcp_probe(host: str, port: int, *, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "connected"
    except Exception as exc:
        return False, str(exc)


def _is_sidecar_json(body: str) -> bool:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and "nim_http_ready" in data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cross-app LipSync NIM connectivity")
    parser.add_argument("--lipsync-name", default=DEFAULT_LIPSYNC_NAME)
    parser.add_argument("--lipsync-subdomain", default=DEFAULT_LIPSYNC_SUBDOMAIN)
    parser.add_argument("--http-port", type=int, default=DEFAULT_LIPSYNC_HTTP_PORT)
    parser.add_argument("--grpc-port", type=int, default=DEFAULT_LIPSYNC_GRPC_PORT)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dump-apps", action="store_true")
    args = parser.parse_args()

    results: list[CheckResult] = []
    domain = (os.environ.get("CDSW_DOMAIN") or "").strip()

    print("=== Cross-app LipSync connectivity validation ===")
    print(f"Deployment model   : {deploy_mode_label()}")
    print(f"Caller pod IP     : {os.environ.get('CDSW_IP_ADDRESS', '<unknown>')}")
    print(f"Caller engine type: {os.environ.get('CDSW_ENGINE_TYPE', '<unknown>')}")
    print(f"Project dir       : {os.environ.get('CDSW_PROJECT_DIR', '/home/cdsw')}")
    print()

    if is_serverless_nim_mode():
        for label, ok, detail, required in validate_serverless_config():
            if not ok and not required:
                mark = "WARN"
                print(f"[{mark}] {label}: {detail}")
                continue
            results.append(CheckResult(label, ok, detail))

        host, port_str = serverless_grpc_address().rsplit(":", 1)
        grpc_ok, grpc_detail = _tcp_probe(host, int(port_str))
        results.append(
            CheckResult(
                "NVCF serverless gRPC TCP",
                grpc_ok,
                f"{host}:{port_str} -> {grpc_detail}",
            )
        )

        if NIM_ENDPOINTS_JSON.exists():
            nim_data = json.loads(NIM_ENDPOINTS_JSON.read_text())
            mode = nim_data.get("deploy_mode")
            results.append(
                CheckResult(
                    "Serverless nim_endpoints.json",
                    mode == "SERVERLESS",
                    json.dumps(nim_data.get("lipsync", {})),
                )
            )
        else:
            results.append(
                CheckResult(
                    "Serverless nim_endpoints.json",
                    False,
                    f"Run Wire Service Endpoints first (expected {NIM_ENDPOINTS_JSON})",
                )
            )

        print("--- Results ---")
        failures = sum(1 for r in results if not r.ok)
        for r in results:
            mark = "PASS" if r.ok else "FAIL"
            print(f"[{mark}] {r.name}: {r.detail}")
        print()
        if failures:
            print("Tips:")
            print("  - Serverless mode needs NGC_API_KEY only; ASD uses a baked-in NVCF catalog ID")
            print("  - LipSync serverless needs a function ID from NVIDIA AI for Media if not in catalog")
            print("  - Run Wire Service Endpoints after S2S is running")
        return 1 if failures else 0

    try:
        project_id = _project_id()
        client = _make_cml_client()
        apps = _list_applications(client, project_id)
        results.append(CheckResult("CML API list_applications", True, f"{len(apps)} application(s)"))

        if args.dump_apps:
            print("--- Applications (API) ---")
            print(json.dumps(apps, indent=2, default=str))
            print()

        lipsync = _find_lipsync_app(apps, name=args.lipsync_name, subdomain=args.lipsync_subdomain)
        if not lipsync:
            results.append(
                CheckResult(
                    "Find LipSync application",
                    False,
                    f"No app matching name={args.lipsync_name!r} subdomain~={args.lipsync_subdomain!r}",
                )
            )
        else:
            results.append(
                CheckResult(
                    "Find LipSync application",
                    True,
                    f"id={lipsync.get('id')} status={lipsync.get('status')} "
                    f"subdomain={lipsync.get('subdomain')}",
                )
            )
            if domain and lipsync.get("subdomain"):
                public_url = f"https://{lipsync['subdomain']}.{domain}/"
                code, body = _http_probe(public_url)
                sidecar_ok = _is_sidecar_json(body)
                results.append(
                    CheckResult(
                        "Public LipSync sidecar JSON",
                        sidecar_ok,
                        f"GET {public_url} -> HTTP {code}; "
                        + (
                            f"body={body[:200]!r}"
                            if sidecar_ok
                            else "expected JSON with nim_http_ready (got HTML or other body)"
                        ),
                    )
                )
    except Exception as exc:
        results.append(CheckResult("CML API discovery", False, str(exc)))

    nim_data: dict[str, Any] = {}
    if NIM_ENDPOINTS_JSON.exists():
        nim_data = json.loads(NIM_ENDPOINTS_JSON.read_text())
    lipsync_entry = nim_data.get("lipsync") or nim_data.get("lipsync-nim") or {}
    wired_host = lipsync_entry.get("host")
    wired_http = int(lipsync_entry.get("http_port", args.http_port))
    wired_grpc = int(lipsync_entry.get("grpc_port", args.grpc_port))

    if wired_host and IP_RE.match(str(wired_host)):
        results.append(
            CheckResult("AMP nim_endpoints.json (LipSync)", True, json.dumps(lipsync_entry)),
        )
        health_url = f"http://{wired_host}:{wired_http}/v1/health/ready"
        code, body = _http_probe(health_url)
        results.append(
            CheckResult(
                "Cross-pod NIM HTTP health",
                code == 200,
                f"GET {health_url} -> HTTP {code}; body={body[:200]!r}",
            )
        )
        grpc_ok, grpc_detail = _tcp_probe(str(wired_host), wired_grpc)
        results.append(
            CheckResult(
                "Cross-pod NIM gRPC TCP",
                grpc_ok,
                f"{wired_host}:{wired_grpc} -> {grpc_detail}",
            )
        )
    else:
        results.append(
            CheckResult(
                "AMP nim_endpoints.json (LipSync)",
                False,
                f"Missing at {NIM_ENDPOINTS_JSON} (written after NIM /v1/health/ready in LipSync app)",
            )
        )

    print("--- Results ---")
    failures = sum(1 for r in results if not r.ok)
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.name}: {r.detail}")

    print()
    if failures:
        print("Tips:")
        print("  - Run cai/amp/0_spike/verify_ngc_access.py first if model cache stays at 4K")
        print("  - LipSync Application Logs: cai/config/lipsync_nim.log on shared project storage")
        print("  - Sidecar log: cai/config/lipsync_sidecar.log")
    return 1 if failures else 0


run_amp_entry(main, __name__)
