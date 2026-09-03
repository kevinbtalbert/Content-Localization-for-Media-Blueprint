"""NIM deployment mode: bundled GPU NIMs vs NVIDIA serverless (NVCF) APIs."""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path

from cai.lib.paths import NIM_ENDPOINTS_JSON, PROJECT_ROOT
from cai.lib.tls_paths import default_ssl_root_cert_path

# Keep in sync with src/common/nvcf.py (controller reads that module after PYTHONPATH setup).
DEFAULT_ASD_NVCF_FUNCTION_ID = "f286f937-05c4-454b-8312-fba67a2a6fa7"
DEFAULT_LIPSYNC_NVCF_FUNCTION_ID = ""


class NIMDeployMode(str, Enum):
    """How LipSync and ASD inference are reached in this CAI deployment."""

    BUNDLED = "BUNDLED"
    SERVERLESS = "SERVERLESS"


def normalize_nim_deploy_mode(raw: str | None = None) -> NIMDeployMode:
    """Resolve ``NIM_DEPLOY_MODE`` (and legacy aliases) to a deploy mode."""
    if raw is None:
        raw = os.environ.get("NIM_DEPLOY_MODE", "").strip()

    if not raw:
        use_serverless = os.environ.get("USE_SERVERLESS_NIMS", "").strip().lower()
        if use_serverless in {"1", "true", "yes", "on"}:
            return NIMDeployMode.SERVERLESS
        deploy_nims = os.environ.get("DEPLOY_NIMS", "").strip().lower()
        if deploy_nims in {"0", "false", "no", "off"}:
            return NIMDeployMode.SERVERLESS
        return NIMDeployMode.BUNDLED

    token = raw.strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "BUNDLED": NIMDeployMode.BUNDLED,
        "BUNDLE": NIMDeployMode.BUNDLED,
        "GPU": NIMDeployMode.BUNDLED,
        "DEPLOY_NIMS": NIMDeployMode.BUNDLED,
        "SERVERLESS": NIMDeployMode.SERVERLESS,
        "NVCF": NIMDeployMode.SERVERLESS,
        "USE_SERVERLESS": NIMDeployMode.SERVERLESS,
        "USE_SERVERLESS_NIMS": NIMDeployMode.SERVERLESS,
    }
    if token in aliases:
        return aliases[token]
    raise ValueError(
        f"Invalid NIM_DEPLOY_MODE={raw!r}. Use BUNDLED (local GPU NIM apps) or SERVERLESS (NVCF APIs)."
    )


def get_nim_deploy_mode() -> NIMDeployMode:
    """Return the active NIM deployment mode for this project."""
    return normalize_nim_deploy_mode()


def is_serverless_nim_mode() -> bool:
    """True when LipSync/ASD should use NVIDIA serverless APIs (no GPU NIM apps)."""
    return get_nim_deploy_mode() == NIMDeployMode.SERVERLESS


def is_bundled_nim_mode() -> bool:
    """True when LipSync/ASD run as bundled GPU applications in CAI."""
    return not is_serverless_nim_mode()


def deploy_mode_label() -> str:
    """Human-readable label for logs and AMP step output."""
    if is_serverless_nim_mode():
        return "NVIDIA serverless NIM APIs (NVCF, no GPU NIM applications)"
    return "bundled LipSync/ASD GPU NIM applications (ContentLocalization runtime)"


def skip_message(step_name: str) -> str:
    """Standard skip banner for AMP steps that do not apply in serverless mode."""
    return (
        f"Skipping '{step_name}' — NIM_DEPLOY_MODE=SERVERLESS "
        "(LipSync/ASD use NVIDIA serverless APIs; no local GPU NIM apps)."
    )


def serverless_grpc_host() -> str:
    return os.environ.get("NVIDIA_SERVERLESS_GRPC_HOST", "grpc.nvcf.nvidia.com").strip()


def serverless_grpc_port() -> int:
    return int(os.environ.get("NVIDIA_SERVERLESS_GRPC_PORT", "443"))


def serverless_grpc_address() -> str:
    return f"{serverless_grpc_host()}:{serverless_grpc_port()}"


def lipsync_function_id() -> str:
    override = os.environ.get("LIPSYNC_NVIDIA_FUNCTION_ID", "").strip()
    return override or DEFAULT_LIPSYNC_NVCF_FUNCTION_ID


def asd_function_id() -> str:
    override = os.environ.get("ASD_NVIDIA_FUNCTION_ID", "").strip()
    return override or DEFAULT_ASD_NVCF_FUNCTION_ID


def validate_serverless_config() -> list[tuple[str, bool, str, bool]]:
    """Return (label, ok, detail, required) tuples for serverless checks."""
    results: list[tuple[str, bool, str, bool]] = []
    ngc = os.environ.get("NGC_API_KEY", "").strip()
    results.append(
        (
            "NGC_API_KEY set",
            bool(ngc),
            f"{len(ngc)} chars" if ngc else "required for NVCF authentication",
            True,
        )
    )
    lip_fn = lipsync_function_id()
    results.append(
        (
            "LipSync NVCF function ID",
            bool(lip_fn),
            lip_fn
            or (
                "not in public catalog yet — set LIPSYNC_NVIDIA_FUNCTION_ID if NVIDIA "
                "provided one via AI for Media private access"
            ),
            False,
        )
    )
    asd_fn = asd_function_id()
    results.append(
        (
            "ASD NVCF function ID",
            bool(asd_fn),
            asd_fn or "missing catalog default",
            True,
        )
    )
    results.append(
        (
            "Serverless gRPC endpoint",
            True,
            serverless_grpc_address(),
            True,
        )
    )
    return results


def write_serverless_nim_endpoints_json(path: Path | None = None) -> Path:
    """Write nim_endpoints.json describing NVCF targets (no local pod IPs)."""
    target = path or NIM_ENDPOINTS_JSON
    host = serverless_grpc_host()
    port = serverless_grpc_port()
    address = f"{host}:{port}"
    payload = {
        "deploy_mode": NIMDeployMode.SERVERLESS.value,
        "lipsync": {
            "host": host,
            "grpc_port": port,
            "http_port": 0,
            "grpc_address": address,
            "function_id": lipsync_function_id(),
            "source": "nvcf_serverless",
        },
        "asd": {
            "host": host,
            "grpc_port": port,
            "http_port": 0,
            "grpc_address": address,
            "function_id": asd_function_id(),
            "source": "nvcf_serverless",
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n")
    return target


def serverless_runtime_endpoints() -> dict[str, str]:
    """Build runtime_endpoints.env entries for serverless LipSync/ASD."""
    address = serverless_grpc_address()
    endpoints: dict[str, str] = {
        "LIPSYNC_SERVER": address,
        "CONTROLLER_LIPSYNC_SSL_MODE": "TLS",
        "ASD_SERVER": address,
        "CONTROLLER_ASD_SSL_MODE": "TLS",
        "CONTROLLER_NIM_SSL_ROOT_CERT": default_ssl_root_cert_path(),
        "NIM_DEPLOY_MODE": NIMDeployMode.SERVERLESS.value,
    }
    lip_fn = lipsync_function_id()
    if lip_fn:
        endpoints["LIPSYNC_NVIDIA_FUNCTION_ID"] = lip_fn
    asd_fn = asd_function_id()
    if asd_fn:
        endpoints["ASD_NVIDIA_FUNCTION_ID"] = asd_fn
    return endpoints


def project_deploy_mode_report_path() -> Path:
    return PROJECT_ROOT / "cai" / "config" / "nim_deploy_mode.json"


def write_deploy_mode_report() -> Path:
    """Persist the resolved deploy mode for diagnostics."""
    path = project_deploy_mode_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nim_deploy_mode": get_nim_deploy_mode().value,
        "serverless_grpc_address": serverless_grpc_address() if is_serverless_nim_mode() else None,
        "lipsync_function_id_set": bool(lipsync_function_id()),
        "asd_function_id_set": bool(asd_function_id()),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
