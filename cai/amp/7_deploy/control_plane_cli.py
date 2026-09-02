#!/usr/bin/env python3
"""CLI for the demo UI deployment control plane (invoked from Next.js API routes)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.app_config import AppConfig, load_app_config, save_app_config  # noqa: E402
from cai.lib.deployment_control import deploy_stack, list_deployment_status  # noqa: E402


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
        config = AppConfig.merge_update(load_app_config(), data)
        path = save_app_config(config)
        print(
            json.dumps(
                {
                    "saved": str(path),
                    "config": config.public_dict(),
                    "secrets_set": config.secrets_set(),
                },
                indent=2,
            )
        )
        return 0

    if args.command == "deploy":
        config = load_app_config()
        if config is None:
            print(json.dumps({"error": "Save configuration before deploying."}), file=sys.stderr)
            return 1
        result = deploy_stack(config)
        print(json.dumps(result, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
