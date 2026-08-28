"""Tests for CAI GPU worker placement helpers."""

from cai.lib.gpu_config import (
    GPU_NODE_LABEL_OPTIONS,
    apply_gpu_env_to_worker_groups,
    resolve_gpu_node_label,
)


def test_resolve_gpu_node_label_auto_a10g():
    assert resolve_gpu_node_label("A10G") == {
        "nvidia.com/gpu.product": "NVIDIA-A10G"
    }


def test_resolve_gpu_node_label_known_t4():
    assert resolve_gpu_node_label("T4") == {
        "nvidia.com/gpu.product": GPU_NODE_LABEL_OPTIONS["T4"]
    }


def test_resolve_gpu_node_label_custom_override():
    assert resolve_gpu_node_label("A10G", "NVIDIA-L40S") == {
        "nvidia.com/gpu.product": "NVIDIA-L40S"
    }


def test_resolve_gpu_node_label_disabled():
    assert resolve_gpu_node_label("A10G", "none") is None


def test_apply_gpu_env_to_worker_groups(monkeypatch):
    monkeypatch.setenv("RAY_GPU_ACCELERATOR_TYPE", "L40S")
    monkeypatch.setenv("RAY_GPU_NODE_LABEL_VALUE", "")
    monkeypatch.setenv("RAY_NIM_GPU_WORKER_COUNT", "2")
    groups = [{"name": "nim-gpu-workers", "count": 1, "accelerator_type": "A10G"}]
    apply_gpu_env_to_worker_groups(groups)
    assert groups[0]["accelerator_type"] == "L40S"
    assert groups[0]["node_label"]["nvidia.com/gpu.product"] == "NVIDIA-L40S"
    assert groups[0]["count"] == 2
