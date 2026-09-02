#!/usr/bin/env python3
"""CLI for the Launchpad pipeline control plane (invoked from Next.js API routes)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.app_config import AppConfig, load_app_config, save_app_config, validate_merged_config  # noqa: E402
from cai.lib.build_progress import is_build_in_progress  # noqa: E402
from cai.lib.deployment_control import build_pipeline, list_deployment_status  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Content Localization pipeline control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Pipeline status, service apps, and build progress")

    save_parser = sub.add_parser("save-config", help="Persist Launchpad configuration")
    save_parser.add_argument("--config-json", required=True, help="JSON configuration")

    validate_parser = sub.add_parser("validate", help="Validate configuration before building")
    validate_parser.add_argument("--config-json", default="", help="Optional unsaved form JSON to merge")

    sub.add_parser("build", help="Validate and build the pipeline (blocking; use from background worker)")
    sub.add_parser("deploy", help="Alias for build")

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

    if args.command == "validate":
        patch = json.loads(args.config_json) if args.config_json else None
        result = validate_merged_config(patch)
        print(json.dumps(result, indent=2))
        return 0 if result.get("valid") else 1

    if args.command in {"build", "deploy"}:
        if is_build_in_progress():
            print(json.dumps({"error": "A pipeline build is already in progress."}), file=sys.stderr)
            return 1
        config = load_app_config()
        if config is None:
            print(json.dumps({"error": "Save configuration before building."}), file=sys.stderr)
            return 1
        validation = config.validate_for_build()
        if not validation["valid"]:
            print(json.dumps({"error": "; ".join(validation["errors"]), **validation}), file=sys.stderr)
            return 1
        try:
            result = build_pipeline(config)
            print(json.dumps(result, indent=2))
        except Exception as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
