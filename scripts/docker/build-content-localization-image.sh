#!/usr/bin/env bash
# Build the ContentLocalization image with NIM model weights baked in.
#
# Required:
#   export NGC_API_KEY=...
#
# Optional:
#   CONTENT_LOCALIZATION_VERSION=1.6.0
#   CONTENT_LOCALIZATION_REPO=content-localization
#   CONTENT_LOCALIZATION_REGISTRY=<registry>/<namespace>/content-localization   # optional private registry tag
#   CONTENT_LOCALIZATION_IMAGE=...   # full override — disables auto arch suffix
#   NIM_PREFETCH_GPU=all             # passed through to prefetch
#
# Auto-tags (when CONTENT_LOCALIZATION_IMAGE is unset):
#   content-localization:1.6.0-turing
#   (+ registry tag when CONTENT_LOCALIZATION_REGISTRY is set)
#
#   ./scripts/docker/build-content-localization-image.sh [docker build args...]
#
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${root}"

# shellcheck source=scripts/docker/nim-gpu-arch.sh
source "${root}/scripts/docker/nim-gpu-arch.sh"

VERSION="${CONTENT_LOCALIZATION_VERSION:-1.6.0}"
REPO="${CONTENT_LOCALIZATION_REPO:-content-localization}"
REGISTRY="${CONTENT_LOCALIZATION_REGISTRY:-}"
META_DIR="${root}/build/nim-model-cache"
NIM_PREFETCH_GPU="${NIM_PREFETCH_GPU:-all}"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: export NGC_API_KEY before building." >&2
  exit 1
fi

echo "=== Content Localization image build ==="
echo "  Version:  ${VERSION}"
echo "  Repo:     ${REPO}"
if [[ -n "${REGISTRY}" ]]; then
  echo "  Registry: ${REGISTRY}"
fi
echo

echo "Step 1/2: Prefetch LipSync + ASD model caches (requires GPU + docker on this host) ..."
"${root}/scripts/docker/prefetch-nim-model-caches.sh"

arch="$(nim_read_gpu_arch "${META_DIR}" "${NIM_PREFETCH_GPU}")"

if [[ -n "${CONTENT_LOCALIZATION_IMAGE:-}" ]]; then
  NIM_IMAGE_TAGS=("${CONTENT_LOCALIZATION_IMAGE}")
  echo "Using explicit CONTENT_LOCALIZATION_IMAGE=${CONTENT_LOCALIZATION_IMAGE}"
else
  nim_compose_image_tags "${REPO}" "${VERSION}" "${arch}" "${REGISTRY}"
  echo "Auto-tagged for GPU arch '${arch}':"
  for tag in "${NIM_IMAGE_TAGS[@]}"; do
    echo "  - ${tag}"
  done
fi

echo
echo "Step 2/2: docker build ..."
build_args=(docker build --platform linux/amd64)
tag=""
for tag in "${NIM_IMAGE_TAGS[@]}"; do
  build_args+=(-t "${tag}")
done
build_args+=("$@" .)

"${build_args[@]}"

echo
echo "=== Build complete ==="
for tag in "${NIM_IMAGE_TAGS[@]}"; do
  echo "  ${tag}"
done
if [[ -f "${META_DIR}/.build-metadata" ]]; then
  echo
  echo "GPU metadata:"
  sed 's/^/  /' "${META_DIR}/.build-metadata"
fi
echo
echo "Baked model caches: /opt/nvidia-nim/baked-model-cache/"
if [[ -n "${REGISTRY}" ]]; then
  primary="${REGISTRY}:${VERSION}"
  [[ "${arch}" != "unknown" ]] && primary="${primary}-${arch}"
  echo "Push: docker push ${primary}"
fi
