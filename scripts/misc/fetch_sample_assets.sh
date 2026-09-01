#!/usr/bin/env bash
# Download sample MP4 assets from the upstream NVIDIA blueprint (not stored in git).
#
# Usage:
#   bash scripts/misc/fetch_sample_assets.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ASSETS_DIR="$REPO_ROOT/assets"

UPSTREAM_BASE="https://media.githubusercontent.com/media/NVIDIA-AI-Blueprints/content-localization/main/assets"

mkdir -p "$ASSETS_DIR"

fetch_one() {
  local name="$1"
  local dest="$ASSETS_DIR/$name"
  local url="$UPSTREAM_BASE/$name"

  if [[ -f "$dest" ]] && [[ "$(head -c 20 "$dest" 2>/dev/null || true)" != "version https://git-" ]]; then
    echo "Already present: $dest"
    return 0
  fi

  echo "Downloading $name ..."
  curl -fsSL "$url" -o "$dest.tmp"
  mv "$dest.tmp" "$dest"
  echo "  -> $dest ($(du -h "$dest" | cut -f1))"
}

fetch_one "sample_video.mp4"
fetch_one "sample_video_streamable.mp4"

echo "Sample videos ready under $ASSETS_DIR/"
