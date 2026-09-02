"""Build and manage the Content Localization pipeline from the Launchpad."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cai.lib.app_config import (
    AppConfig,
    DEPLOYMENT_CONFIG_JSON,
    load_app_config,
    save_app_config,
    validate_merged_config,
)
from cai.lib.build_progress import (
    finish_build_progress,
    is_build_in_progress,
    read_build_progress,
    set_step,
    start_build_progress,
)
from cai.lib.cai_common import write_dotenv_file
from cai.lib.cml_client import ApplicationInfo, CMLClient
from cai.lib.deploy_mode import NIMDeployMode, serverless_runtime_endpoints
from cai.lib.paths import CONFIG_DIR, ENDPOINTS_ENV, PROJECT_ROOT

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


def build_plan(config: AppConfig) -> list[dict[str, str]]:
    """Ordered steps shown in the Launchpad build progress UI."""
    steps = [
        {"id": "validate", "label": "Validate configuration"},
        {"id": "save", "label": "Save configuration"},
    ]
    if config.nim_deploy_mode == NIMDeployMode.SERVERLESS.value:
        steps.append(
            {
                "id": "serverless_nims",
                "label": "Point LipSync & ASD at NVIDIA NVCF (serverless — no project apps)",
            }
        )
    else:
        steps.extend(
            [
                {"id": "lipsync", "label": "Start LipSync NIM application (GPU)"},
                {"id": "asd", "label": "Start ASD NIM application (GPU)"},
            ]
        )
    steps.extend(
        [
            {"id": "s2s", "label": "Start Speech-to-Speech service in this project"},
            {"id": "wait_s2s", "label": "Wait for Speech-to-Speech to publish its endpoint"},
            {"id": "wire", "label": "Connect pipeline services (write runtime endpoints)"},
            {"id": "controller", "label": "Start Controller service in this project"},
            {"id": "ready", "label": "Wait until the pipeline is ready to use"},
        ]
    )
    return steps


def mode_summary(config: AppConfig | None) -> dict[str, str]:
    if config is None:
        return {
            "headline": "Configure your pipeline, then build it from this page.",
            "detail": "Nothing is deployed until you click Build pipeline.",
        }
    if config.nim_deploy_mode == NIMDeployMode.SERVERLESS.value:
        return {
            "headline": "Serverless: LipSync & ASD run on NVIDIA NVCF (not in this project).",
            "detail": (
                "Build still starts Speech-to-Speech and Controller applications here and wires "
                "them to NVCF. Stay on this page — progress updates in real time."
            ),
        }
    return {
        "headline": "Bundled: LipSync & ASD run as GPU applications in this project.",
        "detail": (
            "Build creates four backend applications (LipSync, ASD, Speech-to-Speech, Controller). "
            "GPU NIMs can take a long time; this page polls until everything is ready."
        ),
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


def _wait_for_file(
    path: Path,
    timeout_s: int = 900,
    on_tick: Callable[[int], None] | None = None,
) -> None:
    started = time.time()
    deadline = started + timeout_s
    while time.time() < deadline:
        if path.exists():
            return
        if on_tick:
            on_tick(int(time.time() - started))
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for {path}")


def _wait_for_bundled_nim_endpoints(
    timeout_s: int = 1200,
    on_tick: Callable[[int], None] | None = None,
) -> None:
    nim_path = PROJECT_ROOT / "cai" / "nim_endpoints.json"
    started = time.time()
    deadline = started + timeout_s
    while time.time() < deadline:
        if nim_path.exists():
            data = json.loads(nim_path.read_text())
            if (data.get("lipsync") or data.get("lipsync-nim")) and (
                data.get("asd") or data.get("asd-nim")
            ):
                return
        if on_tick:
            on_tick(int(time.time() - started))
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for LipSync and ASD in {nim_path}")


def _wait_for_pipeline_ready(timeout_s: int = 900) -> None:
    started = time.time()
    deadline = started + timeout_s
    while time.time() < deadline:
        status = list_deployment_status()
        if status.get("pipeline_ready"):
            detail = status.get("controller_address") or "connected"
            set_step("ready", "running", detail=f"Controller at {detail}")
            return
        controller = status.get("services", {}).get("controller", {}).get("application")
        ctrl_status = controller.get("status") if controller else "starting"
        elapsed = int(time.time() - started)
        set_step("ready", "running", detail=f"Controller status: {ctrl_status} ({elapsed}s)")
        time.sleep(10)
    raise TimeoutError("Timed out waiting for the pipeline to become ready")


def wire_service_endpoints(
    config: AppConfig,
    *,
    wait_s2s: bool = True,
    wait_nims: bool = True,
    on_tick: Callable[[int], None] | None = None,
) -> dict[str, str]:
    """Write runtime_endpoints.env from running service metadata."""
    config.apply_to_environ()
    s2s_path = CONFIG_DIR / "s2s_endpoint.json"
    nim_path = PROJECT_ROOT / "cai" / "nim_endpoints.json"

    if wait_s2s:
        _wait_for_file(s2s_path, on_tick=on_tick)
    elif not s2s_path.exists():
        raise FileNotFoundError(f"Missing S2S endpoint file: {s2s_path}")

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
        if wait_nims:
            _wait_for_bundled_nim_endpoints(on_tick=on_tick)
        elif not nim_path.exists():
            raise FileNotFoundError(f"Missing NIM endpoints file: {nim_path}")
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


def _fail_build(step_id: str, message: str) -> None:
    set_step(step_id, "error", detail=message)
    finish_build_progress(False, message)


def build_pipeline(config: AppConfig | None = None) -> dict[str, Any]:
    """Validate, save, and build the pipeline with live progress tracking."""
    if is_build_in_progress():
        raise RuntimeError("A pipeline build is already in progress.")

    if config is None:
        config = load_app_config()
    if config is None:
        raise ValueError("Save your configuration before building.")

    steps = build_plan(config)
    start_build_progress(config.nim_deploy_mode, steps)
    app_results: list[dict[str, Any]] = []

    try:
        set_step("validate", "running", message="Checking required keys and settings…")
        validation = config.validate_for_build()
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        set_step("validate", "done")

        set_step("save", "running", message="Writing configuration to disk…")
        save_app_config(config)
        set_step("save", "done")

        client = CMLClient()
        apps = client.list_applications()

        if config.nim_deploy_mode == NIMDeployMode.SERVERLESS.value:
            set_step(
                "serverless_nims",
                "running",
                message="Configuring NVCF endpoints for LipSync and ASD…",
            )
            config.apply_to_environ()
            from cai.lib.deploy_mode import write_serverless_nim_endpoints_json

            write_serverless_nim_endpoints_json()
            set_step("serverless_nims", "done", detail="Using NVIDIA hosted NVCF APIs")
        else:
            for key in ("lipsync", "asd"):
                set_step(key, "running", message=f"Creating or restarting {SERVICE_SPECS[key]['name']}…")
                result = _ensure_application(client, key, config, apps)
                app_results.append(result)
                set_step(key, "done", detail=f"{result['action']} ({result.get('status', 'unknown')})")
            apps = client.list_applications()

        set_step("s2s", "running", message="Creating or restarting Speech-to-Speech service…")
        s2s_result = _ensure_application(client, "s2s", config, apps)
        app_results.append(s2s_result)
        set_step("s2s", "done", detail=f"{s2s_result['action']} ({s2s_result.get('status', 'unknown')})")

        set_step(
            "wait_s2s",
            "running",
            message="Waiting for Speech-to-Speech — this often takes several minutes…",
        )

        def tick_s2s(elapsed: int) -> None:
            set_step("wait_s2s", "running", detail=f"Waiting for S2S endpoint ({elapsed}s elapsed)")

        _wait_for_file(CONFIG_DIR / "s2s_endpoint.json", on_tick=tick_s2s)
        set_step("wait_s2s", "done")

        set_step("wire", "running", message="Connecting pipeline endpoints…")

        def tick_wire(elapsed: int) -> None:
            if config.nim_deploy_mode == NIMDeployMode.BUNDLED.value:
                set_step("wire", "running", detail=f"Waiting for GPU NIM endpoints ({elapsed}s elapsed)")
            else:
                set_step("wire", "running", detail="Writing serverless + S2S endpoints")

        endpoints = wire_service_endpoints(
            config,
            wait_s2s=False,
            wait_nims=config.nim_deploy_mode == NIMDeployMode.BUNDLED.value,
            on_tick=tick_wire if config.nim_deploy_mode == NIMDeployMode.BUNDLED.value else None,
        )
        set_step("wire", "done", detail="Runtime endpoints saved")

        set_step("controller", "running", message="Creating or restarting Controller service…")
        apps = client.list_applications()
        controller_result = _ensure_application(client, "controller", config, apps)
        app_results.append(controller_result)
        set_step(
            "controller",
            "done",
            detail=f"{controller_result['action']} ({controller_result.get('status', 'unknown')})",
        )

        set_step("ready", "running", message="Waiting for the full pipeline to become ready…")
        _wait_for_pipeline_ready()
        set_step("ready", "done", detail="Pipeline is ready")

        finish_build_progress(True, "Pipeline build completed successfully.")
        return {
            "applications": app_results,
            "endpoints": endpoints,
            "nim_deploy_mode": config.nim_deploy_mode,
        }
    except Exception as exc:
        progress = read_build_progress()
        phase = progress.get("phase") if progress else "validate"
        _fail_build(str(phase), str(exc))
        raise


def list_deployment_status() -> dict[str, Any]:
    config = load_app_config()
    client = CMLClient()
    apps = client.list_applications()
    services: dict[str, Any] = {}
    for key, spec in SERVICE_SPECS.items():
        app = _find_app(apps, spec["name"])
        is_serverless = config and config.nim_deploy_mode == NIMDeployMode.SERVERLESS.value
        if spec["bundled_only"] and is_serverless:
            services[key] = {
                "name": spec["name"],
                "configured": False,
                "skipped_reason": "serverless — uses NVCF instead of a project application",
                "application": None,
            }
        else:
            services[key] = {
                "name": spec["name"],
                "configured": True,
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
    pipeline_ready = has_pipeline_endpoints and bool(controller_app)
    build = read_build_progress()

    return {
        "config_saved": config is not None,
        "config": config.public_dict() if config else None,
        "secrets_set": config.secrets_set() if config else {},
        "nim_deploy_mode": config.nim_deploy_mode if config else None,
        "mode_summary": mode_summary(config),
        "build_plan_preview": build_plan(config) if config else [],
        "services": services,
        "endpoints_ready": endpoints_ready and has_pipeline_endpoints,
        "controller_address": controller_address,
        "pipeline_ready": pipeline_ready,
        "ready_for_demo": pipeline_ready,
        "build": build,
        "build_in_progress": is_build_in_progress(),
        "config_path": str(DEPLOYMENT_CONFIG_JSON),
    }


def deploy_stack(config: AppConfig) -> dict[str, Any]:
    """Backward-compatible alias for build_pipeline."""
    return build_pipeline(config)
