#!/usr/bin/env bash
# Download LipSync/ASD model caches on your laptop for manual upload to CAI.
#
# Preferred for CAI: bake weights into the runtime image instead:
#   ./scripts/docker/prefetch-nim-model-caches.sh
#   ./scripts/docker/build-content-localization-image.sh
#
# Use this script only if you cannot rebuild the runtime image and need to
# upload volumes/models/* to the project by hand.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${root}"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: export NGC_API_KEY before running (same key as docker login nvcr.io)." >&2
  exit 1
fi

mkdir -p volumes/models/lipsync volumes/models/asd

echo "=== LipSync model download (Ctrl+C after cache grows and health is OK) ==="
echo "Cache: ${root}/volumes/models/lipsync"
./scripts/nims/deploy_lipsync.sh

echo
echo "=== ASD model download (Ctrl+C after cache grows and health is OK) ==="
echo "Cache: ${root}/volumes/models/asd"
./scripts/nims/deploy_asd.sh

echo
echo "Done. Upload volumes/models/lipsync and volumes/models/asd to your CAI project."
