"""Run NVIDIA NIM microservices bundled in the ContentLocalization image."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from cai.lib.cai_common import merge_nim_endpoints
from cai.lib.prerequisite_checks import get_ngc_api_key

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
NIM_BUNDLE_ROOT = Path(os.environ.get("NIM_BUNDLE_ROOT", "/opt/nvidia-nim"))
RUN_BUNDLED_NIM = Path("/usr/local/bin/run-bundled-nim")

LIPSYNC_DEFAULTS = {
    "source_image": "nvcr.io/nim/nvidia/lipsync:1.3.0",
    "http_port": 8004,
    "grpc_port": 50054,
    "cache_dir": "/var/lib/content-localization/models/lipsync",
}
ASD_DEFAULTS = {
    "source_image": "nvcr.io/nim/nvidia/active-speaker-detection:1.1.0",
    "http_port": 8005,
    "grpc_port": 50055,
    "cache_dir": "/var/lib/content-localization/models/asd",
}


def pod_ip() -> str:
    return os.environ.get("CDSW_IP_ADDRESS") or socket.gethostbyname(socket.gethostname())


def nim_bundle_path(nim_type: str) -> Path:
    return NIM_BUNDLE_ROOT / nim_type


def nim_bundle_ready(nim_type: str) -> bool:
    return (nim_bundle_path(nim_type) / "entrypoint").is_file()


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
        wait_for_nim_health(http_port)
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
    api_key = get_ngc_api_key()
    if not api_key:
        raise RuntimeError("NGC_API_KEY must be set in project environment")

    http_port = os.environ.get("LIPSYNC_NIM_HTTP_API_PORT", str(LIPSYNC_DEFAULTS["http_port"]))
    grpc_port = os.environ.get("LIPSYNC_NIM_GRPC_API_PORT", str(LIPSYNC_DEFAULTS["grpc_port"]))
    cache_dir = os.environ.get("LIPSYNC_MODEL_MOUNT_PATH", LIPSYNC_DEFAULTS["cache_dir"])
    tags = os.environ.get("LIPSYNC_NIM_TAGS_SELECTOR", "language=de")

    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    env = {
        "NGC_API_KEY": api_key,
        "NIM_HTTP_API_PORT": http_port,
        "NIM_GRPC_API_PORT": grpc_port,
        "NIM_TAGS_SELECTOR": tags,
        "NIM_MAX_CONCURRENCY_PER_GPU": os.environ.get("NIM_MAX_CONCURRENCY_PER_GPU", "1"),
        "NIM_CACHE_DIR": cache_dir,
        "LIPSYNC_DEBUG_MODE": os.environ.get("LIPSYNC_DEBUG_MODE", "0"),
    }
    os.environ.update(env)
    return {
        "nim_type": "lipsync",
        "name": "lipsync-nim",
        "http_port": int(http_port),
        "grpc_port": int(grpc_port),
        "cache_dir": cache_dir,
        "source_image": os.environ.get("LIPSYNC_IMAGE", LIPSYNC_DEFAULTS["source_image"]),
    }


def configure_asd_env() -> dict[str, Any]:
    api_key = get_ngc_api_key()
    if not api_key:
        raise RuntimeError("NGC_API_KEY must be set in project environment")

    http_port = os.environ.get("ASD_NIM_HTTP_API_PORT", str(ASD_DEFAULTS["http_port"]))
    grpc_port = os.environ.get("ASD_GRPC_API_PORT", str(ASD_DEFAULTS["grpc_port"]))
    cache_dir = os.environ.get("ASD_MODEL_MOUNT_PATH", ASD_DEFAULTS["cache_dir"])

    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    env = {
        "NGC_API_KEY": api_key,
        "NIM_HTTP_API_PORT": http_port,
        "NIM_GRPC_API_PORT": grpc_port,
        "MAXINE_MAX_CONCURRENCY_PER_GPU": "1",
        "NIM_MAX_CONCURRENCY_PER_GPU": os.environ.get("NIM_MAX_CONCURRENCY_PER_GPU", "1"),
        "NIM_CACHE_DIR": cache_dir,
    }
    os.environ.update(env)
    return {
        "nim_type": "asd",
        "name": "asd-nim",
        "http_port": int(http_port),
        "grpc_port": int(grpc_port),
        "cache_dir": cache_dir,
        "source_image": os.environ.get("ASD_IMAGE", ASD_DEFAULTS["source_image"]),
    }


def exec_nim_server(nim_type: str) -> None:
    if not nim_bundle_ready(nim_type):
        raise RuntimeError(
            f"Bundled NIM server for '{nim_type}' is missing under {nim_bundle_path(nim_type)}. "
            "Rebuild and re-register the ContentLocalization runtime image (see Dockerfile)."
        )
    if not RUN_BUNDLED_NIM.is_file():
        raise RuntimeError(f"Missing launcher script: {RUN_BUNDLED_NIM}")

    cmd = [str(RUN_BUNDLED_NIM), nim_type]
    print(f"Starting bundled NIM: {' '.join(cmd)}")
    os.execv(cmd[0], cmd)


def write_nim_image_manifest() -> Path:
    manifest = {
        "bundle_strategy": "dockerfile_multistage",
        "bundle_root": str(NIM_BUNDLE_ROOT),
        "note": (
            "LipSync and ASD NIM servers are copied into the ContentLocalization runtime "
            "image at build time. CAI GPU applications use the same registered runtime."
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
    api_key = get_ngc_api_key()
    if not api_key:
        raise RuntimeError(
            "NGC_API_KEY must be set in AMP Configure Project or "
            "Project Settings → Advanced → Environment"
        )
    return api_key
