"""Tests for CAI GPU detection helpers."""

from __future__ import annotations

import json

from cai.lib.gpu_config import (
    GpuProfile,
    configure_worker_groups_gpu,
    load_gpu_profile,
    parse_gpu_name,
    save_gpu_profile,
)


def test_parse_gpu_name_a10g():
    profile = parse_gpu_name("NVIDIA A10G")
    assert profile.accelerator_type == "A10G"
    assert profile.node_label["nvidia.com/gpu.product"] == "NVIDIA-A10G"


def test_parse_gpu_name_tesla_t4():
    profile = parse_gpu_name("Tesla T4")
    assert profile.accelerator_type == "T4"
    assert profile.node_label["nvidia.com/gpu.product"] == "NVIDIA-Tesla-T4"


def test_parse_gpu_name_l40s():
    profile = parse_gpu_name("NVIDIA L40S")
    assert profile.accelerator_type == "L40S"
    assert profile.node_label["nvidia.com/gpu.product"] == "NVIDIA-L40S"


def test_save_and_load_gpu_profile(tmp_path, monkeypatch):
    monkeypatch.setattr("cai.lib.gpu_config.GPU_PROFILE_JSON", tmp_path / "gpu_profile.json")
    profile = GpuProfile(
        gpu_name="NVIDIA A10G",
        accelerator_type="A10G",
        node_label={"nvidia.com/gpu.product": "NVIDIA-A10G"},
    )
    save_gpu_profile(profile)
    loaded = load_gpu_profile()
    assert loaded == profile


def test_configure_worker_groups_gpu_from_saved_profile(tmp_path, monkeypatch):
    profile_path = tmp_path / "gpu_profile.json"
    monkeypatch.setattr("cai.lib.gpu_config.GPU_PROFILE_JSON", profile_path)
    profile_path.write_text(
        json.dumps(
            {
                "gpu_name": "NVIDIA A10G",
                "accelerator_type": "A10G",
                "node_label": {"nvidia.com/gpu.product": "NVIDIA-A10G"},
            }
        )
        + "\n"
    )

    groups = [{"name": "nim-gpu-workers", "count": 1}]
    monkeypatch.delenv("RAY_NIM_GPU_WORKER_COUNT", raising=False)
    configure_worker_groups_gpu(groups)
    assert groups[0]["accelerator_type"] == "A10G"
    assert groups[0]["node_label"]["nvidia.com/gpu.product"] == "NVIDIA-A10G"


def test_configure_worker_groups_gpu_worker_count(tmp_path, monkeypatch):
    profile_path = tmp_path / "gpu_profile.json"
    monkeypatch.setattr("cai.lib.gpu_config.GPU_PROFILE_JSON", profile_path)
    profile_path.write_text(
        json.dumps(
            {
                "gpu_name": "NVIDIA A10G",
                "accelerator_type": "A10G",
                "node_label": {"nvidia.com/gpu.product": "NVIDIA-A10G"},
            }
        )
        + "\n"
    )
    monkeypatch.setenv("RAY_NIM_GPU_WORKER_COUNT", "2")

    groups = [{"name": "nim-gpu-workers", "count": 1}]
    configure_worker_groups_gpu(groups)
    assert groups[0]["count"] == 2
