"""Resolve downstream gRPC endpoints for the Controller at application startup."""

from __future__ import annotations

import json
import os
import shlex
import time
from pathlib import Path

from cai.lib.cai_common import load_dotenv_file, write_dotenv_file
from cai.lib.deploy_mode import (
    NIMDeployMode,
    get_nim_deploy_mode,
    serverless_runtime_endpoints,
)
from cai.lib.paths import CONFIG_DIR, ENDPOINTS_ENV, NIM_ENDPOINTS_JSON, PROJECT_ROOT

CONTROLLER_ENDPOINTS_ENV = CONFIG_DIR / "controller_endpoints.env"


def _grpc_address(data: dict, *, host_key: str = "host", port_key: str = "port") -> str | None:
    if data.get("grpc_address"):
        return str(data["grpc_address"])
    host = data.get(host_key)
    port = data.get(port_key) or data.get("grpc_port")
    if host and port:
        return f"{host}:{port}"
    return None


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_downstream_endpoints() -> dict[str, str]:
    """Build S2S / NIM endpoint map from runtime env and endpoint metadata files."""
    endpoints = load_dotenv_file(ENDPOINTS_ENV)

    if not endpoints.get("S2S_SERVER"):
        s2s_data = _read_json(CONFIG_DIR / "s2s_endpoint.json")
        address = _grpc_address(s2s_data)
        if address:
            endpoints["S2S_SERVER"] = address

    mode = get_nim_deploy_mode()
    if mode == NIMDeployMode.SERVERLESS:
        for key, value in serverless_runtime_endpoints().items():
            endpoints.setdefault(key, value)
    else:
        nim_data = _read_json(NIM_ENDPOINTS_JSON)
        if not nim_data:
            nim_data = _read_json(PROJECT_ROOT / "cai" / "nim_endpoints.json")

        lipsync = nim_data.get("lipsync") or nim_data.get("lipsync-nim") or {}
        asd = nim_data.get("asd") or nim_data.get("asd-nim") or {}

        if not endpoints.get("LIPSYNC_SERVER"):
            address = _grpc_address(lipsync, port_key="grpc_port")
            if address:
                endpoints["LIPSYNC_SERVER"] = address
        if not endpoints.get("ASD_SERVER"):
            address = _grpc_address(asd, port_key="grpc_port")
            if address:
                endpoints["ASD_SERVER"] = address
        endpoints.setdefault("NIM_DEPLOY_MODE", NIMDeployMode.BUNDLED.value)

    return endpoints


def _missing_required(endpoints: dict[str, str]) -> list[str]:
    missing: list[str] = []
    if not endpoints.get("S2S_SERVER"):
        missing.append("S2S_SERVER")
    if not endpoints.get("LIPSYNC_SERVER"):
        missing.append("LIPSYNC_SERVER")
    return missing


def wait_for_downstream_endpoints(*, timeout_s: int = 600) -> dict[str, str]:
    """Poll until S2S and LipSync endpoints are available."""
    deadline = time.time() + timeout_s
    last_missing: list[str] = []
    while time.time() < deadline:
        endpoints = resolve_downstream_endpoints()
        last_missing = _missing_required(endpoints)
        if not last_missing:
            return endpoints
        time.sleep(10)
    summary = ", ".join(last_missing)
    raise TimeoutError(
        f"Timed out waiting for controller downstream endpoints ({summary}). "
        "Ensure Speech-to-Speech is running and LipSync/ASD endpoints are published "
        f"({NIM_ENDPOINTS_JSON} or NVCF settings)."
    )


def write_controller_shell_env(endpoints: dict[str, str]) -> Path:
    """Write shell exports for launch_controller.sh."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    keys = (
        "S2S_SERVER",
        "LIPSYNC_SERVER",
        "ASD_SERVER",
        "NIM_DEPLOY_MODE",
        "CONTROLLER_LIPSYNC_SSL_MODE",
        "CONTROLLER_ASD_SSL_MODE",
        "CONTROLLER_NIM_SSL_ROOT_CERT",
    )
    lines = ["# Generated for Controller launcher — do not edit"]
    for key in keys:
        value = endpoints.get(key) or os.environ.get(key)
        if value:
            lines.append(f"export {key}={shlex.quote(str(value))}")
    CONTROLLER_ENDPOINTS_ENV.write_text("\n".join(lines) + "\n")
    return CONTROLLER_ENDPOINTS_ENV


def prepare_controller_launch_env(*, wait_s: int = 600) -> dict[str, str]:
    """
    Resolve downstream endpoints, persist runtime_endpoints.env, and write shell exports.
    """
    endpoints = wait_for_downstream_endpoints(timeout_s=wait_s)
    write_dotenv_file(ENDPOINTS_ENV, endpoints)
    write_controller_shell_env(endpoints)
    return endpoints
