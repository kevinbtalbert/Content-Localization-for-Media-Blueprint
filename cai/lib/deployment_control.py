"""Deploy Content Localization services from the demo UI via CML API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from cai.lib.app_config import (
    AppConfig,
    DEPLOYMENT_CONFIG_JSON,
    load_app_config,
    save_app_config,
)
from cai.lib.cai_common import write_dotenv_file
from cai.lib.cml_client import ApplicationInfo, CMLClient
from cai.lib.deploy_mode import NIMDeployMode, serverless_runtime_endpoints
from cai.lib.paths import CONFIG_DIR, ENDPOINTS_ENV, PROJECT_ROOT

# Backward-compatible aliases
DeploymentConfig = AppConfig
load_deployment_config = load_app_config
save_deployment_config = save_app_config

SERVICE_SPECS: dict[str, dict[str, Any]] = {
    "lipsync": {
        "name": "LipSync NIM",
        "subdomain": "cl-lipsync",
        "script": "cai/amp/4_services/launch_lipsync_nim.py",
        "cpu": 4,
        "memory": 32,
        "gpu": 1,
        "bundled_only": True,
    },
    "asd": {
        "name": "ASD NIM",
        "subdomain": "cl-asd",
        "script": "cai/amp/4_services/launch_asd_nim.py",
        "cpu": 4,
        "memory": 32,
        "gpu": 1,
        "bundled_only": True,
    },
    "s2s": {
        "name": "Speech-to-Speech Service",
        "subdomain": "cl-s2s",
        "script": "cai/amp/4_services/launch_s2s.py",
        "cpu": 2,
        "memory": 4,
        "gpu": 0,
        "bundled_only": False,
    },
    "controller": {
        "name": "Controller Service",
        "subdomain": "cl-controller",
        "script": "cai/amp/4_services/launch_controller.py",
        "cpu": 4,
        "memory": 8,
        "gpu": 0,
        "bundled_only": False,
    },
}


def _find_app(apps: list[ApplicationInfo], name: str) -> ApplicationInfo | None:
    for app in apps:
        if app.name == name:
            return app
    return None


def _ensure_application(
    client: CMLClient,
    spec_key: str,
    config: AppConfig,
    apps: list[ApplicationInfo],
) -> dict[str, Any]:
    spec = SERVICE_SPECS[spec_key]
    existing = _find_app(apps, spec["name"])
    env = config.app_environment()

    if existing:
        status = (existing.status or "").upper()
        if status in {"RUNNING", "APPLICATION_RUNNING"}:
            return {
                "service": spec_key,
                "action": "exists",
                "id": existing.id,
                "status": existing.status,
            }
        restarted = client.restart_application(existing.id)
        return {
            "service": spec_key,
            "action": "restarted" if restarted else "restart_failed",
            "id": existing.id,
            "status": existing.status,
        }

    created = client.create_application(
        name=spec["name"],
        script=spec["script"],
        subdomain=spec["subdomain"],
        cpu=spec["cpu"],
        memory=spec["memory"],
        gpu=spec["gpu"],
        environment=env,
    )
    return {
        "service": spec_key,
        "action": "created",
        "id": created.id,
        "status": created.status,
    }


def _wait_for_file(path: Path, timeout_s: int = 900) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if path.exists():
            return
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for {path}")


def _wait_for_bundled_nim_endpoints(timeout_s: int = 1200) -> None:
    nim_path = PROJECT_ROOT / "cai" / "nim_endpoints.json"
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not nim_path.exists():
            time.sleep(10)
            continue
        data = json.loads(nim_path.read_text())
        if (data.get("lipsync") or data.get("lipsync-nim")) and (
            data.get("asd") or data.get("asd-nim")
        ):
            return
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for LipSync and ASD in {nim_path}")


def wire_service_endpoints(config: AppConfig) -> dict[str, str]:
    """Write runtime_endpoints.env from running service metadata."""
    config.apply_to_environ()
    s2s_path = CONFIG_DIR / "s2s_endpoint.json"
    nim_path = PROJECT_ROOT / "cai" / "nim_endpoints.json"

    _wait_for_file(s2s_path)
    s2s_data = json.loads(s2s_path.read_text())
    endpoints: dict[str, str] = {
        "S2S_SERVER": s2s_data.get(
            "grpc_address", f"{s2s_data['host']}:{s2s_data['port']}"
        ),
    }

    if config.nim_deploy_mode == NIMDeployMode.SERVERLESS.value:
        from cai.lib.deploy_mode import write_serverless_nim_endpoints_json

        write_serverless_nim_endpoints_json()
        endpoints.update(serverless_runtime_endpoints())
    else:
        _wait_for_bundled_nim_endpoints()
        nim_data = json.loads(nim_path.read_text())
        lipsync = nim_data.get("lipsync") or nim_data.get("lipsync-nim", {})
        asd = nim_data.get("asd") or nim_data.get("asd-nim", {})
        endpoints.update(
            {
                "LIPSYNC_SERVER": lipsync.get(
                    "grpc_address", f"{lipsync.get('host')}:{lipsync.get('grpc_port')}"
                ),
                "ASD_SERVER": asd.get(
                    "grpc_address", f"{asd.get('host')}:{asd.get('grpc_port')}"
                ),
                "NIM_DEPLOY_MODE": NIMDeployMode.BUNDLED.value,
            }
        )

    write_dotenv_file(ENDPOINTS_ENV, endpoints)
    return endpoints


def list_deployment_status() -> dict[str, Any]:
    config = load_app_config()
    client = CMLClient()
    apps = client.list_applications()
    services: dict[str, Any] = {}
    for key, spec in SERVICE_SPECS.items():
        app = _find_app(apps, spec["name"])
        services[key] = {
            "name": spec["name"],
            "configured": not spec["bundled_only"]
            or (config and config.nim_deploy_mode == NIMDeployMode.BUNDLED.value),
            "application": (
                {"id": app.id, "status": app.status, "subdomain": app.subdomain}
                if app
                else None
            ),
        }

    endpoints_ready = ENDPOINTS_ENV.exists()
    controller_address = None
    has_pipeline_endpoints = False
    if endpoints_ready:
        endpoint_values = {}
        for line in ENDPOINTS_ENV.read_text().splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            endpoint_values[key.strip()] = value.strip().strip('"')
        controller_address = endpoint_values.get("CONTROLLER_SERVER")
        has_pipeline_endpoints = bool(
            endpoint_values.get("S2S_SERVER") and endpoint_values.get("LIPSYNC_SERVER")
        )

    controller_app = services.get("controller", {}).get("application")

    return {
        "config_saved": config is not None,
        "config": config.public_dict() if config else None,
        "secrets_set": config.secrets_set() if config else {},
        "nim_deploy_mode": config.nim_deploy_mode if config else None,
        "services": services,
        "endpoints_ready": endpoints_ready and has_pipeline_endpoints,
        "controller_address": controller_address,
        "ready_for_demo": has_pipeline_endpoints and bool(controller_app),
        "config_path": str(DEPLOYMENT_CONFIG_JSON),
    }


def deploy_stack(config: AppConfig) -> dict[str, Any]:
    save_app_config(config)
    client = CMLClient()
    apps = client.list_applications()

    deploy_keys: list[str]
    if config.nim_deploy_mode == NIMDeployMode.BUNDLED.value:
        deploy_keys = ["lipsync", "asd", "s2s"]
    else:
        deploy_keys = ["s2s"]

    app_results = [_ensure_application(client, key, config, apps) for key in deploy_keys]

    endpoints = wire_service_endpoints(config)

    apps = client.list_applications()
    controller_result = _ensure_application(client, "controller", config, apps)
    app_results.append(controller_result)

    return {
        "applications": app_results,
        "endpoints": endpoints,
        "nim_deploy_mode": config.nim_deploy_mode,
    }
