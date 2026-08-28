"""GPU worker placement helpers for Ray cluster launch on CAI."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

# Common nvidia.com/gpu.product values (verify on your cluster).
GPU_NODE_LABEL_OPTIONS: Dict[str, str] = {
    "A10G": "NVIDIA-A10G",
    "L40S": "NVIDIA-L40S",
    "L4": "NVIDIA-L4",
    "T4": "NVIDIA-Tesla-T4",
    "A100": "NVIDIA-A100",
    "H100": "NVIDIA-H100",
}

DEFAULT_GPU_ACCELERATOR_TYPE = "A10G"
DEFAULT_NIM_GPU_WORKER_COUNT = 2
GPU_NODE_LABEL_KEY = "nvidia.com/gpu.product"


def _strip(value: Optional[str]) -> str:
    return (value or "").strip()


def resolve_gpu_node_label(
    accelerator_type: str,
    node_label_value: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Return a K8s node selector dict, or None to skip GPU SKU placement."""
    override = _strip(node_label_value)
    if override.lower() in {"none", "skip", "disabled", "off"}:
        return None
    if override:
        return {GPU_NODE_LABEL_KEY: override}

    acc = _strip(accelerator_type).upper()
    if not acc:
        return None

    product = GPU_NODE_LABEL_OPTIONS.get(acc, f"NVIDIA-{acc}")
    return {GPU_NODE_LABEL_KEY: product}


def apply_gpu_env_to_worker_groups(worker_groups: List[Dict[str, Any]]) -> None:
    """Apply RAY_GPU_* project env vars to worker_groups in place."""
    if not worker_groups:
        return

    acc_type = os.environ.get("RAY_GPU_ACCELERATOR_TYPE")
    node_label_value = os.environ.get("RAY_GPU_NODE_LABEL_VALUE")
    worker_count = os.environ.get("RAY_NIM_GPU_WORKER_COUNT")

    for group in worker_groups:
        if acc_type is not None:
            group["accelerator_type"] = _strip(acc_type) or None

        effective_acc = group.get("accelerator_type") or DEFAULT_GPU_ACCELERATOR_TYPE
        if node_label_value is not None or acc_type is not None:
            group["node_label"] = resolve_gpu_node_label(
                effective_acc,
                node_label_value,
            )

        if worker_count is not None and _strip(worker_count):
            group["count"] = int(worker_count)
