#!/usr/bin/env python3
"""CML Application: Content Localization Next.js demo UI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
sys.path.insert(0, str(PROJECT_ROOT))

from cai.lib.cai_common import apply_dotenv_to_os  # noqa: E402
from cai.lib.deployment_control import DEPLOYMENT_CONFIG_JSON, DeploymentConfig  # noqa: E402
from cai.lib.paths import ENDPOINTS_ENV  # noqa: E402

DEMO_DIR = PROJECT_ROOT / "client" / "demos"


def main() -> int:
    if DEPLOYMENT_CONFIG_JSON.exists():
        config = DeploymentConfig.from_dict(json.loads(DEPLOYMENT_CONFIG_JSON.read_text()))
        config.apply_to_environ()
    apply_dotenv_to_os(ENDPOINTS_ENV)
    os.environ.setdefault("PORT", os.environ.get("CDSW_APP_PORT", "8080"))
    os.environ.setdefault("NODE_ENV", "production")
    os.environ.setdefault("OUTPUT_DIR", str(PROJECT_ROOT / "volumes" / "demo-app"))
    os.environ.setdefault("INPUT_DIR", str(PROJECT_ROOT / "assets"))

    os.chdir(DEMO_DIR)
    cmd = ["npm", "run", "start"]
    print("Starting demo UI:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
