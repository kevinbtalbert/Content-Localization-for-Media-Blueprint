"""GPU detection and Ray worker placement helpers for CAI."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from cai.lib.paths import CONFIG_DIR

GPU_NODE_LABEL_KEY = "nvidia.com/gpu.product"
DEFAULT_NIM_GPU_WORKER_COUNT = 2
GPU_PROFILE_JSON = CONFIG_DIR / "gpu_profile.json"

# (substring in nvidia-smi gpu_name, Ray accelerator_type, K8s nvidia.com/gpu.product)
_KNOWN_GPU_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("H100", "H100", "NVIDIA-H100"),
    ("A100", "A100", "NVIDIA-A100"),
    ("A10G", "A10G", "NVIDIA-A10G"),
    ("L40S", "L40S", "NVIDIA-L40S"),
    ("TESLA T4", "T4", "NVIDIA-Tesla-T4"),
    ("L4", "L4", "NVIDIA-L4"),
    (" T4", "T4", "NVIDIA-Tesla-T4"),
)


@dataclass(frozen=True)
class GpuProfile:
    gpu_name: str
    accelerator_type: str
    node_label: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GpuProfile":
        return cls(
            gpu_name=str(data["gpu_name"]),
            accelerator_type=str(data["accelerator_type"]),
            node_label=dict(data["node_label"]),
        )


def query_nvidia_smi_gpu_names() -> List[str]:
    """Return GPU product names from nvidia-smi, one per device."""
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def parse_gpu_name(gpu_name: str) -> GpuProfile:
    """Map an nvidia-smi gpu_name to Ray accelerator_type and K8s node label."""
    upper = gpu_name.upper()
    for needle, accelerator_type, product_label in _KNOWN_GPU_PATTERNS:
        if needle in upper:
            return GpuProfile(
                gpu_name=gpu_name.strip(),
                accelerator_type=accelerator_type,
                node_label={GPU_NODE_LABEL_KEY: product_label},
            )

    accelerator_type = _infer_accelerator_type(gpu_name)
    product_label = _infer_node_label_product(gpu_name, accelerator_type)
    return GpuProfile(
        gpu_name=gpu_name.strip(),
        accelerator_type=accelerator_type,
        node_label={GPU_NODE_LABEL_KEY: product_label},
    )


def _infer_accelerator_type(gpu_name: str) -> str:
    """Best-effort short Ray label from nvidia-smi output."""
    tokens = re.findall(r"[A-Za-z]+\d+[A-Za-z0-9]*", gpu_name.upper())
    if tokens:
        return tokens[-1]
    slug = re.sub(r"[^A-Z0-9]+", "", gpu_name.upper())
    return slug or "GPU"


def _infer_node_label_product(gpu_name: str, accelerator_type: str) -> str:
    """Best-effort nvidia.com/gpu.product value from nvidia-smi output."""
    if gpu_name.upper().startswith("NVIDIA "):
        suffix = gpu_name[7:].strip()
        return "NVIDIA-" + suffix.replace(" ", "-")
    if "TESLA" in gpu_name.upper():
        return f"NVIDIA-Tesla-{accelerator_type}"
    return f"NVIDIA-{accelerator_type}"


def detect_gpu_profile() -> Optional[GpuProfile]:
    """Detect GPU profile from nvidia-smi on the current machine."""
    names = query_nvidia_smi_gpu_names()
    if not names:
        return None

    unique = list(dict.fromkeys(names))
    if len(unique) > 1:
        print(
            "Warning: multiple GPU types detected "
            f"({', '.join(unique)}); using {unique[0]} for Ray worker placement"
        )
    profile = parse_gpu_name(unique[0])
    print(
        f"Detected GPU: {profile.gpu_name} "
        f"(accelerator_type={profile.accelerator_type}, "
        f"{GPU_NODE_LABEL_KEY}={profile.node_label[GPU_NODE_LABEL_KEY]})"
    )
    return profile


def save_gpu_profile(profile: GpuProfile, path: Path = GPU_PROFILE_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.to_dict(), indent=2) + "\n")
    return path


def load_gpu_profile(path: Path = GPU_PROFILE_JSON) -> Optional[GpuProfile]:
    if not path.exists():
        return None
    try:
        return GpuProfile.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def apply_gpu_profile_to_worker_groups(
    worker_groups: List[Dict[str, Any]],
    profile: GpuProfile,
) -> None:
    """Apply detected GPU profile to Ray worker group config dicts."""
    for group in worker_groups:
        group["accelerator_type"] = profile.accelerator_type
        group["node_label"] = dict(profile.node_label)


def configure_worker_groups_gpu(worker_groups: List[Dict[str, Any]]) -> Optional[GpuProfile]:
    """
    Resolve GPU placement for worker groups.

    Uses gpu_profile.json written during prerequisite validation (GPU session),
    then tries nvidia-smi on the current host, then leaves placement unset.
    """
    if not worker_groups:
        return None

    profile = load_gpu_profile()
    if profile:
        print(f"Using saved GPU profile from {GPU_PROFILE_JSON}")
    else:
        profile = detect_gpu_profile()
        if profile:
            save_gpu_profile(profile)

    if profile:
        apply_gpu_profile_to_worker_groups(worker_groups, profile)
    else:
        print(
            "Warning: GPU type not detected (no gpu_profile.json and nvidia-smi unavailable). "
            "Ray workers will schedule on any GPU node."
        )

    worker_count = os.environ.get("RAY_NIM_GPU_WORKER_COUNT", "").strip()
    if worker_count:
        count = int(worker_count)
        for group in worker_groups:
            group["count"] = count

    return profile
