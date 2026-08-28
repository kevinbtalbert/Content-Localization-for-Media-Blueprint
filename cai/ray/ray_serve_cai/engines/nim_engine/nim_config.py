"""NVIDIA NIM engine configuration and deployment factory."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from ray import serve

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("nim_image", "nim_type", "grpc_port", "http_port", "model_cache_dir")


class NIMConfigBuilder:
    """Build engine_config for NIM Ray deployments."""

    def build_config(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        is_valid, error = self.validate_config(user_config)
        if not is_valid:
            raise ValueError(f"Invalid NIM configuration: {error}")
        return {
            "nim_image": user_config["nim_image"],
            "nim_type": user_config["nim_type"],
            "grpc_port": int(user_config["grpc_port"]),
            "http_port": int(user_config["http_port"]),
            "model_cache_dir": user_config["model_cache_dir"],
            "nim_tags_selector": user_config.get("nim_tags_selector", ""),
            "ngc_api_key_env": user_config.get("ngc_api_key_env", "NGC_API_KEY"),
            "node_type": user_config.get("node_type"),
            "num_gpus": int(user_config.get("num_gpus", 1)),
            "num_cpus": int(user_config.get("num_cpus", 2)),
            "shm_size": user_config.get("shm_size", "4g"),
            "max_concurrency_per_gpu": int(user_config.get("max_concurrency_per_gpu", 1)),
        }

    def validate_config(self, user_config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        for key in _REQUIRED_KEYS:
            if key not in user_config:
                return False, f"Missing required key: {key}"
        if user_config["nim_type"] not in ("lipsync", "asd"):
            return False, "nim_type must be 'lipsync' or 'asd'"
        return True, None

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "nim_image": "nvcr.io/nim/nvidia/lipsync:1.3.0",
            "nim_type": "lipsync",
            "grpc_port": 50054,
            "http_port": 8004,
            "model_cache_dir": "/home/cdsw/volumes/models/lipsync",
            "nim_tags_selector": "language=de",
            "num_gpus": 1,
            "num_cpus": 2,
        }


class NIMDeploymentFactory:
    """Create Ray Serve application for a NIM deployment."""

    def create_deployment(
        self,
        engine_config: Dict[str, Any],
        num_replicas: int = 1,
        tensor_parallel_size: int = 1,
        use_cpu: bool = False,
        **kwargs,
    ) -> serve.Application:
        from .nim_engine import NIMEngine

        ray_actor_options: Dict[str, Any] = {
            "num_cpus": engine_config.get("num_cpus", 2),
            "num_gpus": 0 if use_cpu else engine_config.get("num_gpus", 1),
        }

        node_type = engine_config.get("node_type")
        if node_type:
            ray_actor_options["resources"] = {f"node_type:{node_type}": 0.001}

        nim_venv = "/home/cdsw/.venv-nim/bin/python"
        from pathlib import Path

        if Path(nim_venv).exists():
            ray_actor_options["runtime_env"] = {"py_executable": nim_venv}

        return NIMEngine.options(
            num_replicas=num_replicas,
            ray_actor_options=ray_actor_options,
        ).bind(engine_config)
