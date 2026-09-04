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
baked_root="/opt/nvidia-nim/baked-model-cache/${nim_type}"
export NIM_CACHE_PATH="${NIM_CACHE_PATH:-${cache_root}}"
mkdir -p "${NIM_CACHE_PATH}"

# Seed writable project cache from image-baked weights (populated at docker build time).
if [[ -d "${baked_root}" ]] && [[ -n "$(ls -A "${baked_root}" 2>/dev/null)" ]]; then
  if [[ -z "$(ls -A "${NIM_CACHE_PATH}" 2>/dev/null)" ]]; then
    echo "Seeding ${nim_type} runtime cache from baked model weights at ${baked_root} ..."
    cp -a "${baked_root}/." "${NIM_CACHE_PATH}/"
    echo "  seeded $(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}')"
  else
    echo "Runtime cache already populated: ${NIM_CACHE_PATH} ($(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}'))"
  fi
else
  echo "WARNING: no baked model cache at ${baked_root}; NIM must download weights at runtime (needs NGC_API_KEY)." >&2
fi

# NVIDIA NIMs read/write model weights at /opt/nim/.cache (see deploy_lipsync.sh).
# docker run uses -v cache:/opt/nim/.cache; bundled mode must recreate that layout.
if [[ ! -d /opt/nim ]]; then
  if ! mkdir -p /opt/nim 2>/dev/null; then
    echo "ERROR: cannot create /opt/nim (need writable /opt or use docker run launcher)." >&2
    exit 1
  fi
fi
if [[ -e /opt/nim/.cache && ! -L /opt/nim/.cache ]]; then
  rm -rf /opt/nim/.cache
fi
if ! ln -sfn "${NIM_CACHE_PATH}" /opt/nim/.cache; then
  echo "ERROR: failed to link /opt/nim/.cache -> ${NIM_CACHE_PATH}" >&2
  exit 1
fi
export NIM_CACHE_DIR="/opt/nim/.cache"

# Also link inside the bundle tree for entrypoints that resolve relative to opt/nim.
bundle_cache="${bundle_root}/opt/nim/.cache"
if [[ -d "${bundle_root}/opt/nim" ]]; then
  if [[ ! -w "${bundle_root}/opt/nim" ]]; then
    echo "WARNING: ${bundle_root}/opt/nim is not writable — skipping bundle cache symlink." >&2
    echo "         Rebuild the ContentLocalization image (see Dockerfile chown on /opt/nvidia-nim)." >&2
  else
    if [[ -e "${bundle_cache}" && ! -L "${bundle_cache}" ]]; then
      rm -rf "${bundle_cache}"
    fi
    if ! ln -sfn "${NIM_CACHE_PATH}" "${bundle_cache}"; then
      echo "WARNING: failed to link ${bundle_cache} -> ${NIM_CACHE_PATH}" >&2
    fi
  fi
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
