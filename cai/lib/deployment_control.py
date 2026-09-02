"""Deploy Content Localization services from the demo UI via CML API."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cai.lib.cai_common import write_dotenv_file
from cai.lib.cml_client import ApplicationInfo, CMLClient
from cai.lib.deploy_mode import NIMDeployMode, serverless_runtime_endpoints
from cai.lib.paths import CONFIG_DIR, ENDPOINTS_ENV, PROJECT_ROOT

DEPLOYMENT_CONFIG_JSON = CONFIG_DIR / "deployment_config.json"

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


@dataclass
class DeploymentConfig:
    nim_deploy_mode: str = "SERVERLESS"
    s2s_service: str = "EL_DUBBING"
    ngc_api_key: str = ""
    elevenlabs_api_key: str = ""
    camb_api_key: str = ""
    lipsync_nim_tags_selector: str = "language=de"
    s2s_default_target_language: str = "de"
    lipsync_nvidia_function_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeploymentConfig:
        return cls(
            nim_deploy_mode=str(data.get("nim_deploy_mode", "SERVERLESS")).upper(),
            s2s_service=str(data.get("s2s_service", "EL_DUBBING")),
            ngc_api_key=str(data.get("ngc_api_key", "")),
            elevenlabs_api_key=str(data.get("elevenlabs_api_key", "")),
            camb_api_key=str(data.get("camb_api_key", "")),
            lipsync_nim_tags_selector=str(
                data.get("lipsync_nim_tags_selector", "language=de")
            ),
            s2s_default_target_language=str(data.get("s2s_default_target_language", "de")),
            lipsync_nvidia_function_id=str(data.get("lipsync_nvidia_function_id", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nim_deploy_mode": self.nim_deploy_mode,
            "s2s_service": self.s2s_service,
            "ngc_api_key": self.ngc_api_key,
            "elevenlabs_api_key": self.elevenlabs_api_key,
            "camb_api_key": self.camb_api_key,
            "lipsync_nim_tags_selector": self.lipsync_nim_tags_selector,
            "s2s_default_target_language": self.s2s_default_target_language,
            "lipsync_nvidia_function_id": self.lipsync_nvidia_function_id,
        }

    def masked_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        for secret_key in ("ngc_api_key", "elevenlabs_api_key", "camb_api_key"):
            value = data.get(secret_key, "")
            data[secret_key] = ("*" * 8) if value else ""
        return data

    def apply_to_environ(self) -> None:
        os.environ["NIM_DEPLOY_MODE"] = self.nim_deploy_mode
        os.environ["S2S_SERVICE"] = self.s2s_service
        if self.ngc_api_key:
            os.environ["NGC_API_KEY"] = self.ngc_api_key
        if self.elevenlabs_api_key:
            os.environ["ELEVENLABS_API_KEY"] = self.elevenlabs_api_key
        if self.camb_api_key:
            os.environ["CAMB_API_KEY"] = self.camb_api_key
        os.environ["LIPSYNC_NIM_TAGS_SELECTOR"] = self.lipsync_nim_tags_selector
        os.environ["S2S_DEFAULT_TARGET_LANGUAGE"] = self.s2s_default_target_language
        if self.lipsync_nvidia_function_id:
            os.environ["LIPSYNC_NVIDIA_FUNCTION_ID"] = self.lipsync_nvidia_function_id

    def app_environment(self) -> dict[str, str]:
        env = {
            "NIM_DEPLOY_MODE": self.nim_deploy_mode,
            "S2S_SERVICE": self.s2s_service,
            "LIPSYNC_NIM_TAGS_SELECTOR": self.lipsync_nim_tags_selector,
            "S2S_DEFAULT_TARGET_LANGUAGE": self.s2s_default_target_language,
            "TASK_TYPE": "START_APPLICATION",
        }
        if self.ngc_api_key:
            env["NGC_API_KEY"] = self.ngc_api_key
        if self.elevenlabs_api_key:
            env["ELEVENLABS_API_KEY"] = self.elevenlabs_api_key
        if self.camb_api_key:
            env["CAMB_API_KEY"] = self.camb_api_key
        if self.lipsync_nvidia_function_id:
            env["LIPSYNC_NVIDIA_FUNCTION_ID"] = self.lipsync_nvidia_function_id
        return env


def load_deployment_config() -> DeploymentConfig | None:
    if not DEPLOYMENT_CONFIG_JSON.exists():
        return None
    return DeploymentConfig.from_dict(json.loads(DEPLOYMENT_CONFIG_JSON.read_text()))


def save_deployment_config(config: DeploymentConfig) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEPLOYMENT_CONFIG_JSON.write_text(json.dumps(config.to_dict(), indent=2) + "\n")
    config.apply_to_environ()
    return DEPLOYMENT_CONFIG_JSON


def _find_app(apps: list[ApplicationInfo], name: str) -> ApplicationInfo | None:
    for app in apps:
        if app.name == name:
            return app
    return None


def _ensure_application(
    client: CMLClient,
    spec_key: str,
    config: DeploymentConfig,
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


def wire_service_endpoints(config: DeploymentConfig) -> dict[str, str]:
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
    config = load_deployment_config()
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
        "config": config.masked_dict() if config else None,
        "nim_deploy_mode": config.nim_deploy_mode if config else None,
        "services": services,
        "endpoints_ready": endpoints_ready and has_pipeline_endpoints,
        "controller_address": controller_address,
        "ready_for_demo": has_pipeline_endpoints and bool(controller_app),
    }


def deploy_stack(config: DeploymentConfig) -> dict[str, Any]:
    save_deployment_config(config)
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
