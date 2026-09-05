"""Run NVIDIA NIM microservices bundled in the ContentLocalization image."""

from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from cai.lib.cai_common import merge_nim_endpoints

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
NIM_BUNDLE_ROOT = Path(os.environ.get("NIM_BUNDLE_ROOT", "/opt/nvidia-nim"))
RUN_BUNDLED_NIM_IMAGE = Path("/usr/local/bin/run-bundled-nim")

LIPSYNC_NIM_ENV_KEYS = (
    "NGC_API_KEY",
    "NIM_HTTP_API_PORT",
    "NIM_GRPC_API_PORT",
    "NIM_TAGS_SELECTOR",
    "NIM_MAX_CONCURRENCY_PER_GPU",
    "NIM_CACHE_PATH",
    "NIM_CACHE_DIR",
    "LIPSYNC_DEBUG_MODE",
)
ASD_NIM_ENV_KEYS = (
    "NGC_API_KEY",
    "NIM_HTTP_API_PORT",
    "NIM_GRPC_API_PORT",
    "MAXINE_MAX_CONCURRENCY_PER_GPU",
    "NIM_MAX_CONCURRENCY_PER_GPU",
    "NIM_CACHE_PATH",
    "NIM_CACHE_DIR",
)

LIPSYNC_DEFAULTS = {
    "source_image": "nvcr.io/nim/nvidia/lipsync:1.3.0",
    "http_port": 8004,
    "grpc_port": 50054,
}
ASD_DEFAULTS = {
    "source_image": "nvcr.io/nim/nvidia/active-speaker-detection:1.1.0",
    "http_port": 8005,
    "grpc_port": 50055,
}


def nim_cache_dir(nim_type: str, env_var: str) -> str:
    """Model weights cache under the CAI project home (/home/cdsw is writable)."""
    project = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
    override = os.environ.get(env_var, "").strip()
    if override.startswith("/home/cdsw"):
        path = Path(override)
    else:
        if override:
            print(
                f"Ignoring {env_var}={override!r} (use a path under /home/cdsw on CAI); "
                f"using {project / 'volumes' / 'models' / nim_type}",
                file=sys.stderr,
            )
        path = project / "volumes" / "models" / nim_type
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def resolve_run_bundled_nim() -> Path:
    """Prefer the project launcher (synced from git) over the image-baked copy."""
    project_script = PROJECT_ROOT / "cai" / "runtime" / "scripts" / "run-bundled-nim.sh"
    if project_script.is_file():
        return project_script
    return RUN_BUNDLED_NIM_IMAGE


def write_nim_shell_env(nim_type: str, keys: tuple[str, ...]) -> Path:
    """Write NIM env vars for `source` by launch shell scripts (Python subprocess cannot export)."""
    path = PROJECT_ROOT / "cai" / "config" / f"{nim_type}_nim.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for key in keys:
        value = os.environ.get(key)
        if value is None:
            continue
        lines.append(f"export {key}={shlex.quote(value)}")
    path.write_text("\n".join(lines) + "\n")
    return path


def pod_ip() -> str:
    return os.environ.get("CDSW_IP_ADDRESS") or socket.gethostbyname(socket.gethostname())


def nim_bundle_path(nim_type: str) -> Path:
    return NIM_BUNDLE_ROOT / nim_type


def nim_bundle_ready(nim_type: str) -> bool:
    return (nim_bundle_path(nim_type) / "entrypoint").is_file()


def tcp_port_open(host: str, port: int, *, timeout_s: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def wait_for_nim_grpc(grpc_port: int, *, host: str = "127.0.0.1", timeout_s: int = 900) -> None:
    """Wait until the Maxine gRPC server is listening (not just nimlib HTTP health)."""
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        if tcp_port_open(host, grpc_port):
            return
        last_error = f"{host}:{grpc_port} not listening"
        time.sleep(5)
    raise TimeoutError(f"NIM gRPC not ready on {host}:{grpc_port}: {last_error}")


def wait_for_nim_ready(
    http_port: int,
    grpc_port: int,
    *,
    timeout_s: int = 900,
    require_grpc: bool = True,
) -> None:
    """Wait for nimlib HTTP ready and (by default) Maxine gRPC to bind."""
    deadline = time.time() + timeout_s
    http_url = f"http://127.0.0.1:{http_port}/v1/health/ready"
    last_error = ""
    while time.time() < deadline:
        http_ok = False
        try:
            with urllib.request.urlopen(http_url, timeout=10) as response:
                http_ok = response.status == 200
        except Exception as exc:  # noqa: BLE001
            last_error = f"http: {exc}"
        grpc_ok = not require_grpc or tcp_port_open("127.0.0.1", grpc_port)
        if http_ok and grpc_ok:
            return
        if http_ok and require_grpc:
            last_error = f"http ready but gRPC :{grpc_port} not listening"
        time.sleep(5)
    raise TimeoutError(f"NIM readiness failed ({http_url}, gRPC :{grpc_port}): {last_error}")


def wait_for_nim_health(http_port: int, *, timeout_s: int = 900) -> None:
    url = f"http://127.0.0.1:{http_port}/v1/health/ready"
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(5)
    raise TimeoutError(f"NIM health check failed for {url}: {last_error}")


def publish_nim_endpoint(
    *,
    name: str,
    nim_type: str,
    grpc_port: int,
    http_port: int,
) -> dict[str, Any]:
    host = pod_ip()
    entry = {
        "host": host,
        "grpc_port": grpc_port,
        "http_port": http_port,
        "grpc_address": f"{host}:{grpc_port}",
        "http_url": f"http://{host}:{http_port}",
        "nim_type": nim_type,
    }
    return merge_nim_endpoints({name: entry, nim_type: entry})


def _background_publish_after_health(
    *,
    name: str,
    nim_type: str,
    grpc_port: int,
    http_port: int,
) -> None:
    try:
        wait_for_nim_ready(http_port, grpc_port)
        data = publish_nim_endpoint(
            name=name,
            nim_type=nim_type,
            grpc_port=grpc_port,
            http_port=http_port,
        )
        print(f"Published NIM endpoint metadata for {nim_type}: {json.dumps(data[nim_type])}")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to publish NIM endpoint metadata for {nim_type}: {exc}", file=sys.stderr)


def start_endpoint_publisher(
    *,
    name: str,
    nim_type: str,
    grpc_port: int,
    http_port: int,
) -> threading.Thread:
    thread = threading.Thread(
        target=_background_publish_after_health,
        kwargs={
            "name": name,
            "nim_type": nim_type,
            "grpc_port": grpc_port,
            "http_port": http_port,
        },
        daemon=True,
    )
    thread.start()
    return thread


def configure_lipsync_env() -> dict[str, Any]:
    api_key = os.environ.get("NGC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("NGC_API_KEY must be set in project environment")

    http_port = os.environ.get("LIPSYNC_NIM_HTTP_API_PORT", str(LIPSYNC_DEFAULTS["http_port"]))
    grpc_port = os.environ.get("LIPSYNC_NIM_GRPC_API_PORT", str(LIPSYNC_DEFAULTS["grpc_port"]))
    cache_dir = nim_cache_dir("lipsync", "LIPSYNC_MODEL_MOUNT_PATH")
    tags = os.environ.get("LIPSYNC_NIM_TAGS_SELECTOR", "language=de")

    env = {
        "NGC_API_KEY": api_key,
        "NIM_HTTP_API_PORT": http_port,
        "NIM_GRPC_API_PORT": grpc_port,
        "NIM_TAGS_SELECTOR": tags,
        "NIM_MAX_CONCURRENCY_PER_GPU": os.environ.get("NIM_MAX_CONCURRENCY_PER_GPU", "1"),
        # Writable project path (monitor with du); NIM process uses /opt/nim/.cache via symlink.
        "NIM_CACHE_PATH": cache_dir,
        "NIM_CACHE_DIR": "/opt/nim/.cache",
        "LIPSYNC_DEBUG_MODE": os.environ.get("LIPSYNC_DEBUG_MODE", "0"),
    }
    os.environ.update(env)
    write_nim_shell_env("lipsync", LIPSYNC_NIM_ENV_KEYS)
    return {
        "nim_type": "lipsync",
        "name": "lipsync-nim",
        "http_port": int(http_port),
        "grpc_port": int(grpc_port),
        "cache_dir": cache_dir,
        "source_image": os.environ.get("LIPSYNC_IMAGE", LIPSYNC_DEFAULTS["source_image"]),
    }


def configure_asd_env() -> dict[str, Any]:
    api_key = os.environ.get("NGC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("NGC_API_KEY must be set in project environment")

    http_port = os.environ.get("ASD_NIM_HTTP_API_PORT", str(ASD_DEFAULTS["http_port"]))
    grpc_port = os.environ.get("ASD_GRPC_API_PORT", str(ASD_DEFAULTS["grpc_port"]))
    cache_dir = nim_cache_dir("asd", "ASD_MODEL_MOUNT_PATH")

    env = {
        "NGC_API_KEY": api_key,
        "NIM_HTTP_API_PORT": http_port,
        "NIM_GRPC_API_PORT": grpc_port,
        "MAXINE_MAX_CONCURRENCY_PER_GPU": "1",
        "NIM_MAX_CONCURRENCY_PER_GPU": os.environ.get("NIM_MAX_CONCURRENCY_PER_GPU", "1"),
        "NIM_CACHE_PATH": cache_dir,
        "NIM_CACHE_DIR": "/opt/nim/.cache",
    }
    os.environ.update(env)
    write_nim_shell_env("asd", ASD_NIM_ENV_KEYS)
    return {
        "nim_type": "asd",
        "name": "asd-nim",
        "http_port": int(http_port),
        "grpc_port": int(grpc_port),
        "cache_dir": cache_dir,
        "source_image": os.environ.get("ASD_IMAGE", ASD_DEFAULTS["source_image"]),
    }


def run_nim_server(nim_type: str) -> int:
    """Start the bundled NIM via shell launcher (blocks until NIM exits)."""
    bundle = nim_bundle_path(nim_type)
    if not nim_bundle_ready(nim_type):
        raise RuntimeError(
            f"Bundled NIM server for '{nim_type}' is missing under {bundle}. "
            "Rebuild and re-register the ContentLocalization runtime image (see Dockerfile)."
        )
    if not resolve_run_bundled_nim().is_file():
        raise RuntimeError(f"Missing launcher script: {resolve_run_bundled_nim()}")

    entrypoint = (bundle / "entrypoint").read_text().strip()
    launcher = resolve_run_bundled_nim()
    cmd = [str(launcher), nim_type]
    print(f"Starting bundled NIM: {' '.join(cmd)}", flush=True)
    print(f"  bundle={bundle}", flush=True)
    print(f"  entrypoint={entrypoint}", flush=True)
    print(f"  NIM_CACHE_PATH={os.environ.get('NIM_CACHE_PATH', '')}", flush=True)
    print(f"  NIM_CACHE_DIR={os.environ.get('NIM_CACHE_DIR', '')}", flush=True)
    return subprocess.call(cmd)


def exec_nim_server(nim_type: str) -> None:
    """Deprecated alias — prefer run_nim_server() for CAI application scripts."""
    raise SystemExit(run_nim_server(nim_type))


def write_nim_image_manifest() -> Path:
    manifest = {
        "bundle_strategy": "dockerfile_multistage",
        "bundle_root": str(NIM_BUNDLE_ROOT),
        "note": (
            "LipSync and ASD NIM servers are copied into the ContentLocalization runtime "
            "image at build time. Model weights are baked under "
            "/opt/nvidia-nim/baked-model-cache/ (see scripts/docker/prefetch-nim-model-caches.sh)."
        ),
        "lipsync": {
            "source_image": os.environ.get("LIPSYNC_IMAGE", LIPSYNC_DEFAULTS["source_image"]),
            "bundle_ready": nim_bundle_ready("lipsync"),
            "bundle_path": str(nim_bundle_path("lipsync")),
        },
        "asd": {
            "source_image": os.environ.get("ASD_IMAGE", ASD_DEFAULTS["source_image"]),
            "bundle_ready": nim_bundle_ready("asd"),
            "bundle_path": str(nim_bundle_path("asd")),
        },
    }
    path = PROJECT_ROOT / "cai" / "config" / "nim_images.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def validate_ngc_for_nim() -> str:
    api_key = os.environ.get("NGC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "NGC_API_KEY must be set in AMP Configure Project or "
            "Project Settings → Advanced → Environment"
        )
    return api_key
