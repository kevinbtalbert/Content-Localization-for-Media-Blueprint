"""Ray Serve deployment that runs a local NVIDIA NIM container on a GPU worker."""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
from ray import serve
from starlette.requests import Request

from ray_serve_cai.engines.engine_utils import create_engine_app, mount_health, mount_metrics

logger = logging.getLogger(__name__)

NIM_ENDPOINTS_PATH = Path("/home/cdsw/cai/nim_endpoints.json")
DOCKER_BIN = os.environ.get("DOCKER_BIN", "docker")


def _pod_ip() -> str:
    return os.environ.get("CDSW_IP_ADDRESS") or socket.gethostbyname(socket.gethostname())


def _tcp_open(host: str, port: int, *, timeout_s: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _wait_for_nim_ready(http_port: int, grpc_port: int, timeout_s: int = 900) -> None:
    url = f"http://127.0.0.1:{http_port}/v1/health/ready"
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        http_ok = False
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                http_ok = response.status == 200
        except Exception as exc:  # noqa: BLE001
            last_error = f"http: {exc}"
        grpc_ok = _tcp_open("127.0.0.1", grpc_port)
        if http_ok and grpc_ok:
            return
        if http_ok:
            last_error = f"gRPC :{grpc_port} not listening"
        time.sleep(5)
    raise TimeoutError(f"NIM readiness failed ({url}, gRPC :{grpc_port}): {last_error}")


def _write_endpoint_metadata(name: str, nim_type: str, grpc_port: int, http_port: int) -> None:
    NIM_ENDPOINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {}
    if NIM_ENDPOINTS_PATH.exists():
        data = json.loads(NIM_ENDPOINTS_PATH.read_text())
    host = _pod_ip()
    entry = {
        "host": host,
        "grpc_port": grpc_port,
        "http_port": http_port,
        "grpc_address": f"{host}:{grpc_port}",
        "http_url": f"http://{host}:{http_port}",
        "nim_type": nim_type,
    }
    data[name] = entry
    data[nim_type] = entry
    NIM_ENDPOINTS_PATH.write_text(json.dumps(data, indent=2) + "\n")
    logger.info("Wrote NIM endpoint metadata: %s", entry)


def _start_nim_container(engine_config: Dict[str, Any]) -> subprocess.Popen[str]:
    api_key = os.environ.get(engine_config.get("ngc_api_key_env", "NGC_API_KEY"), "")
    if not api_key:
        raise RuntimeError("NGC_API_KEY must be set to start NIM containers")

    nim_type = engine_config["nim_type"]
    container_name = f"nim-{nim_type}-{os.getpid()}"
    grpc_port = int(engine_config["grpc_port"])
    http_port = int(engine_config["http_port"])
    cache_dir = Path(engine_config["model_cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        DOCKER_BIN,
        "run",
        "--rm",
        "--name",
        container_name,
        "--runtime=nvidia",
        "--gpus",
        "all",
        f"--shm-size={engine_config.get('shm_size', '4g')}",
        "-e",
        f"NGC_API_KEY={api_key}",
        "-e",
        f"NIM_HTTP_API_PORT={http_port}",
        "-e",
        f"NIM_GRPC_API_PORT={grpc_port}",
        "-e",
        f"NIM_MAX_CONCURRENCY_PER_GPU={engine_config.get('max_concurrency_per_gpu', 1)}",
        "-p",
        f"{http_port}:{http_port}",
        "-p",
        f"{grpc_port}:{grpc_port}",
        "-v",
        f"{cache_dir}:/opt/nim/.cache:rw",
    ]

    if nim_type == "lipsync" and engine_config.get("nim_tags_selector"):
        cmd.extend(["-e", f"NIM_TAGS_SELECTOR={engine_config['nim_tags_selector']}"])
    if nim_type == "asd":
        cmd.extend(["-e", "MAXINE_MAX_CONCURRENCY_PER_GPU=1"])

    cmd.append(engine_config["nim_image"])

    logger.info("Starting NIM container: %s", " ".join(cmd))
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


_app = create_engine_app(title="NVIDIA NIM Engine")
mount_health(_app, engine_type="nim")
mount_metrics(_app)


@_app.get("/v1/nim/endpoint")
async def nim_endpoint() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@serve.deployment
@serve.ingress(_app)
class NIMEngine:
    """Runs a NIM Docker container and exposes health plus endpoint metadata."""

    def __init__(self, engine_config: Dict[str, Any]) -> None:
        self.engine_config = engine_config
        self._process: Optional[subprocess.Popen[str]] = None
        self.name = engine_config.get("name", engine_config["nim_type"])

        self._process = _start_nim_container(engine_config)
        _wait_for_nim_ready(int(engine_config["http_port"]), int(engine_config["grpc_port"]))
        _write_endpoint_metadata(
            self.name,
            engine_config["nim_type"],
            int(engine_config["grpc_port"]),
            int(engine_config["http_port"]),
        )
        logger.info("NIM engine ready: %s", engine_config["nim_type"])

    async def __call__(self, request: Request):
        return JSONResponse(
            {
                "nim_type": self.engine_config["nim_type"],
                "grpc_address": f"{_pod_ip()}:{self.engine_config['grpc_port']}",
            }
        )

    def __del__(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
