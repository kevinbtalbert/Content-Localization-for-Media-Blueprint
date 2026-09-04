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
    deployment_config_load_error,
    load_app_config,
    save_app_config,
    validate_merged_config,
)
from cai.lib.build_progress import (
    BUILD_PROGRESS_JSON,
    finish_build_progress,
    is_build_in_progress,
    read_build_progress,
    reconcile_stale_build,
    set_step,
    start_build_progress,
)
from cai.lib.cai_common import write_dotenv_file
from cai.lib.cml_client import ApplicationInfo, CMLClient
from cai.lib.deploy_mode import NIMDeployMode, serverless_runtime_endpoints
from cai.lib.paths import CONFIG_DIR, ENDPOINTS_ENV, PROJECT_ROOT, ensure_cai_dirs

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
        {"id": "cleanup", "label": "Remove applications from the previous deploy mode"},
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


RUNNING_APP_STATUSES = frozenset({"RUNNING", "APPLICATION_RUNNING"})
FAILED_APP_STATUSES = frozenset(
    {
        "APPLICATION_FAILED",
        "FAILED",
        "STOPPED",
        "APPLICATION_STOPPED",
        "ERROR",
        "APPLICATION_ERROR",
    }
)

STEP_ID_BY_SERVICE = {
    "lipsync": "lipsync",
    "asd": "asd",
    "s2s": "s2s",
    "controller": "controller",
}


def _normalize_app_status(status: str | None) -> str:
    return (status or "").upper()


def _is_app_running(status: str | None) -> bool:
    normalized = _normalize_app_status(status)
    return normalized in RUNNING_APP_STATUSES


def _is_app_failed(status: str | None) -> bool:
    normalized = _normalize_app_status(status)
    return normalized in FAILED_APP_STATUSES or "FAIL" in normalized


def _required_service_keys(config: AppConfig | None) -> list[str]:
    if config and config.nim_deploy_mode == NIMDeployMode.BUNDLED.value:
        return ["lipsync", "asd", "s2s", "controller"]
    return ["s2s", "controller"]


def _collect_failed_services(
    services: dict[str, Any], required_keys: list[str]
) -> list[dict[str, str]]:
    failed: list[dict[str, str]] = []
    for key in required_keys:
        svc = services.get(key, {})
        app = svc.get("application")
        if not app:
            continue
        app_status = app.get("status", "")
        if _is_app_failed(app_status):
            failed.append(
                {
                    "key": key,
                    "name": str(svc.get("name", key)),
                    "status": str(app_status),
                }
            )
    return failed


def _evaluate_pipeline(
    services: dict[str, Any],
    *,
    endpoints_ready: bool,
    required_keys: list[str],
) -> dict[str, Any]:
    failed_services = _collect_failed_services(services, required_keys)
    running_services: list[str] = []
    pending_services: list[str] = []
    missing_services: list[str] = []
    for key in required_keys:
        svc = services.get(key, {})
        app = svc.get("application")
        if not app:
            missing_services.append(str(svc.get("name", key)))
            continue
        app_status = app.get("status", "")
        if _is_app_running(app_status):
            running_services.append(str(svc.get("name", key)))
        elif not _is_app_failed(app_status):
            pending_services.append(f"{svc.get('name', key)} ({app_status})")

    all_running = len(running_services) == len(required_keys) and not pending_services
    pipeline_ready = endpoints_ready and all_running and not failed_services
    pipeline_failed = bool(failed_services)

    return {
        "pipeline_ready": pipeline_ready,
        "pipeline_failed": pipeline_failed,
        "failed_services": failed_services,
        "running_services": running_services,
        "pending_services": pending_services,
        "missing_services": missing_services,
    }


def _reconcile_build_progress(
    services: dict[str, Any], failed_services: list[dict[str, str]]
) -> dict[str, Any] | None:
    """If build progress says success but apps failed, correct the saved progress file."""
    build = read_build_progress()
    if not build or build.get("in_progress") or not failed_services:
        return build

    if build.get("success") is False:
        return build

    summary = "; ".join(f"{item['name']} ({item['status']})" for item in failed_services)
    build = json.loads(json.dumps(build))
    build["success"] = False
    build["error"] = f"Backend not healthy: {summary}"
    build["message"] = build["error"]

    failed_keys = {item["key"] for item in failed_services}
    failed_step_ids = {STEP_ID_BY_SERVICE[k] for k in failed_keys if k in STEP_ID_BY_SERVICE}
    for step in build.get("steps", []):
        step_id = step.get("id", "")
        if step_id in failed_step_ids or step_id in {"ready", "wait_s2s"}:
            step["status"] = "error"
            matching = next(
                (f for f in failed_services if STEP_ID_BY_SERVICE.get(f["key"]) == step_id),
                None,
            )
            if matching:
                step["detail"] = matching["status"]
            elif step_id == "ready":
                step["detail"] = summary

    BUILD_PROGRESS_JSON.write_text(json.dumps(build, indent=2) + "\n")
    return build


def _wait_for_service_running(
    service_key: str,
    *,
    timeout_s: int = 900,
    on_tick: Callable[[int, str], None] | None = None,
) -> None:
    started = time.time()
    deadline = started + timeout_s
    while time.time() < deadline:
        status = list_deployment_status()
        svc = status.get("services", {}).get(service_key, {})
        app = svc.get("application")
        app_status = (app or {}).get("status", "not started")
        if _is_app_failed(app_status):
            raise RuntimeError(f"{svc.get('name', service_key)} failed ({app_status})")
        if _is_app_running(app_status):
            return
        if on_tick:
            on_tick(int(time.time() - started), str(app_status))
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for {service_key} to reach RUNNING")


def _find_app(apps: list[ApplicationInfo], name: str) -> ApplicationInfo | None:
    for app in apps:
        if app.name == name:
            return app
    return None


def _wait_for_app_removed(
    client: CMLClient, name: str, *, timeout_s: int = 180
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        apps = client.list_applications()
        if _find_app(apps, name) is None:
            return
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for application {name!r} to be deleted")


def _clear_runtime_endpoint_artifacts() -> None:
    """Remove stale endpoint metadata before a fresh redeploy."""
    for path in (
        CONFIG_DIR / "s2s_endpoint.json",
        CONFIG_DIR / "controller_endpoint.json",
        ENDPOINTS_ENV,
        CONFIG_DIR / "controller_endpoints.env",
        PROJECT_ROOT / "cai" / "nim_endpoints.json",
    ):
        path.unlink(missing_ok=True)


def _remove_orphaned_pipeline_apps(
    client: CMLClient, config: AppConfig
) -> list[dict[str, str]]:
    """Delete pipeline apps that are not part of the selected deploy mode."""
    required = set(_required_service_keys(config))
    removed: list[dict[str, str]] = []
    for key, spec in SERVICE_SPECS.items():
        if key in required:
            continue
        apps = client.list_applications()
        existing = _find_app(apps, spec["name"])
        if not existing:
            continue
        if not client.delete_application(existing.id):
            raise RuntimeError(f"Failed to delete orphaned application {spec['name']!r}")
        _wait_for_app_removed(client, spec["name"])
        removed.append({"service": key, "name": spec["name"], "id": existing.id})
    return removed


def _ensure_application(
    client: CMLClient,
    spec_key: str,
    config: AppConfig,
    apps: list[ApplicationInfo],
    *,
    recreate: bool = True,
) -> dict[str, Any]:
    spec = SERVICE_SPECS[spec_key]
    existing = _find_app(apps, spec["name"])
    env = config.app_environment()
    had_existing = existing is not None

    if existing and recreate:
        if not client.delete_application(existing.id):
            raise RuntimeError(f"Failed to delete existing application {spec['name']!r}")
        _wait_for_app_removed(client, spec["name"])
        apps = client.list_applications()
        existing = None

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
        "action": "recreated" if had_existing else "created",
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


def _wait_for_pipeline_ready(config: AppConfig, timeout_s: int = 900) -> None:
    required = _required_service_keys(config)
    started = time.time()
    deadline = started + timeout_s
    while time.time() < deadline:
        status = list_deployment_status()
        failed = status.get("failed_services") or []
        if failed:
            summary = "; ".join(f"{f['name']} ({f['status']})" for f in failed)
            raise RuntimeError(f"Pipeline build failed: {summary}")

        if status.get("pipeline_ready"):
            detail = status.get("controller_address") or "all services running"
            set_step("ready", "running", detail=f"Controller at {detail}")
            return

        pending = status.get("pending_services") or []
        elapsed = int(time.time() - started)
        detail = ", ".join(pending) if pending else "waiting for services"
        set_step("ready", "running", detail=f"{detail} ({elapsed}s)")
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
        ensure_cai_dirs()
        set_step("validate", "running", message="Checking required keys and settings…")
        validation = config.validate_for_build()
        if not validation["valid"]:
            raise ValueError("; ".join(validation["errors"]))
        set_step("validate", "done")

        set_step("save", "running", message="Writing configuration to disk…")
        save_app_config(config)
        set_step("save", "done")

        _clear_runtime_endpoint_artifacts()

        client = CMLClient()

        if not client.configure_project_resources():
            print(
                "Warning: could not PATCH project shared_memory_limit; "
                "set Project Settings → Engine → Advanced → 8192 MB manually.",
                flush=True,
            )

        set_step(
            "cleanup",
            "running",
            message="Removing applications not used in this deploy mode…",
        )
        removed = _remove_orphaned_pipeline_apps(client, config)
        if removed:
            detail = ", ".join(item["name"] for item in removed)
            set_step("cleanup", "done", detail=f"Deleted: {detail}")
        else:
            set_step("cleanup", "done", detail="No unused applications to remove")
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
                spec_name = SERVICE_SPECS[key]["name"]
                verb = "Recreating" if _find_app(apps, spec_name) else "Creating"
                set_step(key, "running", message=f"{verb} {spec_name}…")
                result = _ensure_application(client, key, config, apps)
                app_results.append(result)
                set_step(key, "done", detail=f"{result['action']} ({result.get('status', 'unknown')})")
                apps = client.list_applications()

        spec_name = SERVICE_SPECS["s2s"]["name"]
        verb = "Recreating" if _find_app(apps, spec_name) else "Creating"
        set_step("s2s", "running", message=f"{verb} {spec_name}…")
        s2s_result = _ensure_application(client, "s2s", config, apps)
        app_results.append(s2s_result)
        set_step("s2s", "done", detail=f"{s2s_result['action']} ({s2s_result.get('status', 'unknown')})")
        apps = client.list_applications()

        set_step(
            "wait_s2s",
            "running",
            message="Waiting for Speech-to-Speech to reach RUNNING — this can take several minutes…",
        )

        def tick_s2s(elapsed: int, app_status: str) -> None:
            set_step(
                "wait_s2s",
                "running",
                detail=f"Speech-to-Speech status: {app_status} ({elapsed}s elapsed)",
            )

        _wait_for_service_running("s2s", on_tick=tick_s2s)
        if not (CONFIG_DIR / "s2s_endpoint.json").exists():
            _wait_for_file(CONFIG_DIR / "s2s_endpoint.json", timeout_s=120, on_tick=lambda e: tick_s2s(e, "waiting for endpoint file"))
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

        apps = client.list_applications()
        controller_name = SERVICE_SPECS["controller"]["name"]
        verb = "Recreating" if _find_app(apps, controller_name) else "Creating"
        set_step("controller", "running", message=f"{verb} {controller_name}…")
        controller_result = _ensure_application(client, "controller", config, apps)
        app_results.append(controller_result)
        set_step(
            "controller",
            "done",
            detail=f"{controller_result['action']} ({controller_result.get('status', 'unknown')})",
        )

        set_step("ready", "running", message="Waiting for the full pipeline to become ready…")
        _wait_for_pipeline_ready(config)
        set_step("ready", "done", detail="All backend applications are running")

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


def _model_cache_bytes(nim_type: str) -> int:
    cache = PROJECT_ROOT / "volumes" / "models" / nim_type
    if not cache.is_dir():
        return 0
    return sum(path.stat().st_size for path in cache.rglob("*") if path.is_file())


def _model_cache_detail(nim_type: str, app_status: str | None) -> str | None:
    if not app_status:
        return None
    status = app_status.upper()
    if status in {"RUNNING", "APPLICATION_RUNNING"}:
        return None
    total = _model_cache_bytes(nim_type)
    if total >= 1024 * 1024:
        return f"model cache {total / (1024 * 1024):.1f} MB — first start can take 15–120+ min"
    return f"model cache {max(total, 0) / 1024:.0f} KB — downloading weights from NGC (15–120+ min)"


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
            app_status = app.status if app else None
            detail = None
            if key in {"lipsync", "asd"} and app:
                detail = _model_cache_detail(key, app_status)
            services[key] = {
                "name": spec["name"],
                "configured": True,
                "application": (
                    {"id": app.id, "status": app.status, "subdomain": app.subdomain}
                    if app
                    else None
                ),
                "detail": detail,
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

    endpoints_connected = endpoints_ready and has_pipeline_endpoints
    required_keys = _required_service_keys(config)
    pipeline_state = _evaluate_pipeline(
        services,
        endpoints_ready=endpoints_connected,
        required_keys=required_keys,
    )
    reconcile_stale_build(
        pipeline_failed=pipeline_state["pipeline_failed"],
        failed_services=pipeline_state["failed_services"],
        any_deployed_apps=bool(
            pipeline_state["running_services"] or pipeline_state["pending_services"]
        ),
    )
    build = _reconcile_build_progress(services, pipeline_state["failed_services"])
    if build is None:
        build = read_build_progress()

    return {
        "config_saved": config is not None,
        "config_error": deployment_config_load_error(),
        "config": config.public_dict() if config else None,
        "secrets_set": config.secrets_set() if config else {},
        "nim_deploy_mode": config.nim_deploy_mode if config else None,
        "mode_summary": mode_summary(config),
        "build_plan_preview": build_plan(config) if config else [],
        "services": services,
        "endpoints_ready": endpoints_connected,
        "controller_address": controller_address,
        "pipeline_ready": pipeline_state["pipeline_ready"],
        "pipeline_failed": pipeline_state["pipeline_failed"],
        "failed_services": pipeline_state["failed_services"],
        "pending_services": pipeline_state["pending_services"],
        "missing_services": pipeline_state["missing_services"],
        "running_services": pipeline_state["running_services"],
        "ready_for_demo": pipeline_state["pipeline_ready"],
        "build": build,
        "build_in_progress": is_build_in_progress(),
        "deploy_active": is_build_in_progress() or bool(pipeline_state["pending_services"]),
        "config_path": str(DEPLOYMENT_CONFIG_JSON),
    }


def deploy_stack(config: AppConfig) -> dict[str, Any]:
    """Backward-compatible alias for build_pipeline."""
    return build_pipeline(config)
