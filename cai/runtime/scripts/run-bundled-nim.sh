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

cache_default="/var/lib/content-localization/models/${nim_type}"
export NIM_CACHE_DIR="${NIM_CACHE_DIR:-${cache_default}}"
mkdir -p "${NIM_CACHE_DIR}"

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
echo "Starting bundled ${nim_type} NIM: ${entrypoint}"
echo "  NIM_CACHE_DIR=${NIM_CACHE_DIR}"
exec "${entrypoint}"
