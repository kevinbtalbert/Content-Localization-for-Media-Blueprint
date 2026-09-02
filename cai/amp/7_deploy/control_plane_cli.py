#!/usr/bin/env python3
"""CLI for the demo UI deployment control plane (invoked from Next.js API routes)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.deployment_control import (  # noqa: E402
    DeploymentConfig,
    deploy_stack,
    list_deployment_status,
    load_deployment_config,
    save_deployment_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Content Localization deployment control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="List configured services and CML application status")

    save_parser = sub.add_parser("save-config", help="Persist deployment configuration")
    save_parser.add_argument("--config-json", required=True, help="JSON deployment config")

    sub.add_parser("deploy", help="Create/restart service applications and wire endpoints")

    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(list_deployment_status(), indent=2))
        return 0

    if args.command == "save-config":
        data = json.loads(args.config_json)
        existing = load_deployment_config()
        merged = existing.to_dict() if existing else {}
        merged.update(data)
        for secret in ("ngc_api_key", "elevenlabs_api_key", "camb_api_key"):
            if secret in data and not str(data[secret]).strip():
                merged.pop(secret, None)
        config = DeploymentConfig.from_dict(merged)
        path = save_deployment_config(config)
        print(json.dumps({"saved": str(path), "config": config.masked_dict()}, indent=2))
        return 0

    if args.command == "deploy":
        config = load_deployment_config()
        if config is None:
            print(json.dumps({"error": "Save configuration before deploying."}), file=sys.stderr)
            return 1
        result = deploy_stack(config)
        print(json.dumps(result, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
