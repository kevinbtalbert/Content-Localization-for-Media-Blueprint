#!/usr/bin/env python3
"""AMP session: build the Next.js web application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))

from cai.lib.amp_runtime import run_amp_entry  # noqa: E402
from cai.lib.paths import PROJECT_ROOT, ensure_cai_dirs, media_dir  # noqa: E402

DEMO_DIR = PROJECT_ROOT / "client" / "demos"


def main() -> int:
    ensure_cai_dirs()
    print(f"Media folder ready: {media_dir()}", flush=True)
    os.chdir(DEMO_DIR)
    dist = DEMO_DIR / "dist" / "server.js"
    next_dir = DEMO_DIR / ".next"
    media_routes = DEMO_DIR / "dist" / "server" / "mediaRoutes.js"
    next_media_route = next_dir / "server" / "app" / "api" / "media" / "route.js"
    next_videos_route = next_dir / "server" / "app" / "api" / "videos" / "route.js"
    has_media_api = media_routes.is_file() or next_media_route.is_file() or next_videos_route.is_file()
    if (
        dist.is_file()
        and next_dir.is_dir()
        and has_media_api
        and not os.environ.get("FORCE_DEMO_BUILD", "").strip()
    ):
        print(f"✅ Web UI already built ({dist}) — skipping npm build")
        print("   Set FORCE_DEMO_BUILD=1 to rebuild after code changes.")
        return 0

    if dist.is_file() and next_dir.is_dir() and not has_media_api:
        print("⚠️  Existing build is missing /api/media routes — rebuilding Web UI …")

    env = {**os.environ, "NEXT_PUBLIC_INPUT_FILE_NAME": os.environ.get("DEFAULT_INPUT_FILE_NAME", "sample_video.mp4")}
    for cmd in (
        ["npm", "ci"],
        ["npm", "run", "generate-ts-protos"],
        ["npm", "run", "build"],
    ):
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True, env=env)
    print("✅ Web UI built")
    return 0


run_amp_entry(main, __name__)
