#!/usr/bin/env bash
# Launch a NIM microservice from the bundle baked into the ContentLocalization image.
set -euo pipefail

nim_type="${1:?lipsync or asd}"
bundle_root="/opt/nvidia-nim/${nim_type}"
entrypoint_file="${bundle_root}/entrypoint"

if [[ ! -f "${entrypoint_file}" ]]; then
  echo "ERROR: NIM bundle for '${nim_type}' not found at ${bundle_root}." >&2
  echo "Rebuild the ContentLocalization image with NGC access (see Dockerfile)." >&2
  exit 1
fi

cache_root="${CDSW_PROJECT_DIR:-/home/cdsw}/volumes/models/${nim_type}"
export NIM_CACHE_PATH="${NIM_CACHE_PATH:-${NIM_CACHE_DIR:-${cache_root}}}"
export NIM_CACHE_DIR="${NIM_CACHE_DIR:-${NIM_CACHE_PATH}}"
mkdir -p "${NIM_CACHE_PATH}"

# Bundled NIM defaults to /opt/nim/.cache (see NVIDIA LipSync docs). When not using
# Docker volume mounts, point the in-bundle path at the writable project cache.
bundle_cache="${bundle_root}/opt/nim/.cache"
if [[ -d "${bundle_root}/opt/nim" ]]; then
  if [[ -e "${bundle_cache}" && ! -L "${bundle_cache}" ]]; then
    rm -rf "${bundle_cache}"
  fi
  ln -sfn "${NIM_CACHE_PATH}" "${bundle_cache}" 2>/dev/null || true
fi

lib_paths=(
  "${bundle_root}/usr/local/lib"
  "${bundle_root}/usr/local/lib64"
  "${bundle_root}/opt/nim/lib"
  "${bundle_root}/opt/tritonserver/lib"
)
for lib in "${lib_paths[@]}"; do
  if [[ -d "${lib}" ]]; then
    export LD_LIBRARY_PATH="${lib}:${LD_LIBRARY_PATH:-}"
  fi
done

if [[ -d "${bundle_root}/usr/local/bin" ]]; then
  export PATH="${bundle_root}/usr/local/bin:${PATH}"
fi

entrypoint="$(tr -d '\n' <"${entrypoint_file}")"
if [[ ! -e "${entrypoint}" ]]; then
  echo "ERROR: NIM entrypoint not found: ${entrypoint}" >&2
  exit 1
fi
if [[ ! -x "${entrypoint}" ]]; then
  chmod +x "${entrypoint}" 2>/dev/null || true
fi

echo "Starting bundled ${nim_type} NIM: ${entrypoint}"
echo "  NIM_CACHE_PATH=${NIM_CACHE_PATH}"
echo "  NIM_CACHE_DIR=${NIM_CACHE_DIR}"
echo "  NGC_API_KEY set: $([ -n "${NGC_API_KEY:-}" ] && echo yes || echo NO)"
echo "  NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-unset}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi -L || true
fi
exec "${entrypoint}"
