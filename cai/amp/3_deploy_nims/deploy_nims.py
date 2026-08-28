#!/usr/bin/env python3
"""AMP session: deploy ASD and LipSync NIMs via Ray Management API."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.cai_common import get_ray_head_url, wait_for_http  # noqa: E402

CONFIG_DIR = PROJECT_ROOT / "cai" / "ray" / "configs" / "nim_deploy"


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_config(path: Path) -> dict:
    config = json.loads(path.read_text())
    tags = os.environ.get("LIPSYNC_NIM_TAGS_SELECTOR")
    if tags and config.get("engine_config", {}).get("nim_type") == "lipsync":
        config["engine_config"]["nim_tags_selector"] = tags
    return config


def main() -> int:
    head_url = get_ray_head_url()
    wait_for_http(f"{head_url}/api/v1/health", timeout_s=900)

    deploy_url = f"{head_url}/api/v1/applications"
    for config_name in ("lipsync-nim.json", "asd-nim.json"):
        config_path = CONFIG_DIR / config_name
        payload = _load_config(config_path)
        print(f"Deploying {payload['name']}...")
        try:
            result = _post_json(deploy_url, payload)
            print(json.dumps(result, indent=2))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            print(f"Deploy failed ({exc.code}): {body}")
            return 1

        route = payload["route_prefix"].rstrip("/")
        wait_for_http(f"{head_url}{route}/health", timeout_s=1200)

    print("✅ NIM deployments submitted and healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
