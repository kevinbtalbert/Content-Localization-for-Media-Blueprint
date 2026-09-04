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

# CAI may set NVIDIA_VISIBLE_DEVICES=void while nvidia-smi still works; CUDA apps need a device index.
if [[ "${NVIDIA_VISIBLE_DEVICES:-}" == "void" || "${NVIDIA_VISIBLE_DEVICES:-}" == "none" ]]; then
  export NVIDIA_VISIBLE_DEVICES=0
  echo "Adjusted NVIDIA_VISIBLE_DEVICES=0 (was void/none — required for bundled NIM CUDA init)."
fi

cache_min_bytes() {
  case "${nim_type}" in
    lipsync) echo "${NIM_RUNTIME_MIN_BYTES_LIPSYNC:-$((3 * 1024 * 1024 * 1024))}" ;;
    asd) echo "${NIM_RUNTIME_MIN_BYTES_ASD:-$((2 * 1024 * 1024 * 1024))}" ;;
    *) echo "${NIM_RUNTIME_MIN_BYTES:-$((2 * 1024 * 1024 * 1024))}" ;;
  esac
}

dir_bytes() {
  local path="$1"
  if [[ -d "${path}" ]]; then
    du -sb "${path}" 2>/dev/null | awk '{print $1}' || echo 0
  else
    echo 0
  fi
}

min_bytes="$(cache_min_bytes)"
cache_bytes="$(dir_bytes "${NIM_CACHE_PATH}")"
baked_bytes="$(dir_bytes "${baked_root}")"

# Seed writable project cache from image-baked weights (populated at docker build time).
if [[ "${SKIP_BAKED_CACHE:-}" == "1" ]]; then
  echo "SKIP_BAKED_CACHE=1 — not seeding from ${baked_root}."
elif [[ -d "${baked_root}" ]] && [[ -n "$(ls -A "${baked_root}" 2>/dev/null)" ]]; then
  if (( cache_bytes < min_bytes )); then
    if (( baked_bytes >= min_bytes )); then
      echo "Seeding ${nim_type} runtime cache from baked model weights at ${baked_root} ..."
      rm -rf "${NIM_CACHE_PATH:?}/"*
      cp -a "${baked_root}/." "${NIM_CACHE_PATH}/"
      cache_bytes="$(dir_bytes "${NIM_CACHE_PATH}")"
      echo "  seeded $(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}')"
    elif (( baked_bytes >= 1048576 )); then
      echo "WARNING: baked cache at ${baked_root} is only $(du -sh "${baked_root}" | awk '{print $1}') — below expected minimum." >&2
      echo "         Rebuild the runtime image with a full prefetch, or allow runtime download with NGC_API_KEY." >&2
    fi
  else
    echo "Runtime cache already populated: ${NIM_CACHE_PATH} ($(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}'))"
  fi
else
  echo "WARNING: no baked model cache at ${baked_root}; NIM must download weights at runtime (needs NGC_API_KEY)." >&2
fi

cache_bytes="$(dir_bytes "${NIM_CACHE_PATH}")"
if (( cache_bytes < min_bytes )); then
  if [[ -z "${NGC_API_KEY:-}" ]]; then
    echo "ERROR: model cache $(du -sh "${NIM_CACHE_PATH}" 2>/dev/null | awk '{print $1}') is below minimum for ${nim_type}." >&2
    echo "  Set NGC_API_KEY in Project Settings → Environment and restart the session/application." >&2
    echo "  Or rebuild the image with a complete prefetch (see scripts/docker/prefetch-nim-model-caches.sh)." >&2
    exit 1
  fi
  echo "Model cache below minimum ($(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}')); NIM will download from NGC on startup (may take 15–60+ min)."
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
