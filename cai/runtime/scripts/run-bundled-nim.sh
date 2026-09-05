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

# CAI may set NVIDIA_VISIBLE_DEVICES=void while nvidia-smi still works; CUDA apps need a real device.
# Prefer GPU UUID (works when the device node is /dev/nvidia3 but nvidia-smi shows "GPU 0").
if [[ "${NVIDIA_VISIBLE_DEVICES:-}" == "void" || "${NVIDIA_VISIBLE_DEVICES:-}" == "none" || -z "${NVIDIA_VISIBLE_DEVICES:-}" ]]; then
  gpu_uuid="$(nvidia-smi -L 2>/dev/null | sed -n 's/.*UUID: \([^)]*\)).*/\1/p' | head -1 || true)"
  if [[ -n "${gpu_uuid}" ]]; then
    export NVIDIA_VISIBLE_DEVICES="${gpu_uuid}"
    echo "Adjusted NVIDIA_VISIBLE_DEVICES=${gpu_uuid} (CAI void/none — bind by UUID)."
  else
    export NVIDIA_VISIBLE_DEVICES=0
    echo "Adjusted NVIDIA_VISIBLE_DEVICES=0 (was void/none — fallback index)."
  fi
fi

shm_mb="$(df -m /dev/shm 2>/dev/null | awk 'NR==2 {print $2}' || echo 0)"
echo "/dev/shm: $(df -h /dev/shm 2>/dev/null | awk 'NR==2 {print $2 " total, " $3 " used, " $4 " avail"}' || echo unknown)"
if [[ "${shm_mb}" =~ ^[0-9]+$ ]] && (( shm_mb < 4096 )); then
  echo "ERROR: /dev/shm is only ${shm_mb}M — LipSync/ASD Triton needs ~4–8 GB." >&2
  echo "  Project Settings → Engine → Advanced → Shared Memory Limit → 8192 MB" >&2
  echo "  Then delete and recreate LipSync/ASD apps from Launchpad (or Redeploy AMP)." >&2
  exit 1
fi

cache_min_bytes() {
  case "${nim_type}" in
    lipsync) echo "${NIM_RUNTIME_MIN_BYTES_LIPSYNC:-$((500 * 1024 * 1024))}" ;;
    asd) echo "${NIM_RUNTIME_MIN_BYTES_ASD:-$((350 * 1024 * 1024))}" ;;
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
# LipSync language=de is ~650M complete; do not require multi-GB before seeding.
if [[ "${SKIP_BAKED_CACHE:-}" == "1" ]]; then
  echo "SKIP_BAKED_CACHE=1 — not seeding from ${baked_root}."
elif [[ -d "${baked_root}" ]] && [[ -n "$(ls -A "${baked_root}" 2>/dev/null)" ]]; then
  if (( cache_bytes < baked_bytes )); then
    echo "Seeding ${nim_type} runtime cache from baked model weights at ${baked_root} ..."
    rm -rf "${NIM_CACHE_PATH:?}/"* "${NIM_CACHE_PATH:?}/".* 2>/dev/null || true
    cp -a "${baked_root}/." "${NIM_CACHE_PATH}/"
    cache_bytes="$(dir_bytes "${NIM_CACHE_PATH}")"
    echo "  seeded $(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}')"
  else
    echo "Runtime cache already populated: ${NIM_CACHE_PATH} ($(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}'))"
  fi
else
  echo "WARNING: no baked model cache at ${baked_root}; NIM must download weights at runtime (needs NGC_API_KEY)." >&2
fi

cache_bytes="$(dir_bytes "${NIM_CACHE_PATH}")"
# Runtime minimums (~650M LipSync de, ~420M ASD) — see build/nim-model-cache/README.md
if (( cache_bytes < min_bytes )); then
  if [[ -z "${NGC_API_KEY:-}" ]]; then
    echo "ERROR: model cache $(du -sh "${NIM_CACHE_PATH}" 2>/dev/null | awk '{print $1}') is below minimum for ${nim_type}." >&2
    echo "  Set NGC_API_KEY in Project Settings → Environment and restart the session/application." >&2
    echo "  Or rebuild the image with a complete prefetch (see scripts/docker/prefetch-nim-model-caches.sh)." >&2
    exit 1
  fi
  if (( baked_bytes >= 1048576 && cache_bytes >= baked_bytes )); then
    echo "Using baked cache ($(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}')) — size is normal for this NIM profile."
  else
    echo "Model cache below minimum ($(du -sh "${NIM_CACHE_PATH}" | awk '{print $1}')); NIM will download from NGC on startup (may take 15–60+ min)."
  fi
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
  "${bundle_root}/usr/lib/x86_64-linux-gnu"
  "${bundle_root}/usr/lib"
  "${bundle_root}/lib/x86_64-linux-gnu"
  "${bundle_root}/lib"
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

# NIM start_server is a Python script (nimlib). CAI runtime is Python 3.13; the bundle ships
# its own interpreter + site-packages under usr/local/ from the nvcr.io NIM image.
resolve_nim_python() {
  local bundle="$1"
  local py site nimlib_dir
  local -a pythons=() nimlib_dirs=()

  while IFS= read -r nimlib_dir; do
    nimlib_dirs+=("${nimlib_dir}")
  done < <(find "${bundle}" -path '*/dist-packages/nimlib' -type d 2>/dev/null | sort -u)

  while IFS= read -r py; do
    pythons+=("${py}")
  done < <(
    find "${bundle}" \
      \( -path '*/usr/local/bin/python3*' -o -path '*/usr/bin/python3*' -o -path '*/opt/nim/*/bin/python3*' \) \
      -type f 2>/dev/null | sort -u
  )

  for py in "${pythons[@]}"; do
    [[ -x "${py}" ]] || continue
    for nimlib_dir in "${nimlib_dirs[@]}"; do
      site="$(dirname "${nimlib_dir}")"
      if PYTHONPATH="${site}" "${py}" -c "import nimlib" 2>/dev/null; then
        export PYTHONPATH="${site}${PYTHONPATH:+:${PYTHONPATH}}"
        printf '%s\n' "${py}"
        return 0
      fi
    done
  done

  echo "DEBUG: searched ${bundle} for NIM python + nimlib:" >&2
  echo "  nimlib: ${nimlib_dirs[*]:-(none)}" >&2
  echo "  python: ${pythons[*]:-(none)}" >&2
  if [[ -L "${bundle}/usr/local/bin/python3" ]]; then
    echo "  usr/local/bin/python3 -> $(readlink "${bundle}/usr/local/bin/python3" 2>/dev/null || echo broken)" >&2
  fi
  return 1
}

resolve_start_server() {
  local bundle="$1"
  if [[ -f "${bundle}/usr/local/bin/start_server" ]]; then
    printf '%s\n' "${bundle}/usr/local/bin/start_server"
    return 0
  fi
  if [[ -f "${bundle}/opt/nim/start_server.sh" ]]; then
    printf '%s\n' "${bundle}/opt/nim/start_server.sh"
    return 0
  fi
  find "${bundle}" \( -path '*/usr/local/bin/start_server' -o -path '*/opt/nim/start_server.sh' \) -type f 2>/dev/null | head -1
}

entrypoint="$(tr -d '\n' <"${entrypoint_file}")"
if [[ ! -e "${entrypoint}" ]]; then
  echo "ERROR: NIM entrypoint not found: ${entrypoint}" >&2
  exit 1
fi
if [[ ! -x "${entrypoint}" ]]; then
  chmod +x "${entrypoint}" 2>/dev/null || true
fi

start_server="$(resolve_start_server "${bundle_root}")"
nim_python="$(resolve_nim_python "${bundle_root}" || true)"
if [[ -z "${start_server}" || ! -f "${start_server}" ]]; then
  echo "ERROR: could not find NIM start_server under ${bundle_root}." >&2
  echo "  Expected usr/local/bin/start_server or opt/nim/start_server.sh from the NIM image." >&2
  exit 1
fi
if [[ -z "${nim_python}" ]]; then
  echo "ERROR: bundled NIM Python with nimlib not found under ${bundle_root}." >&2
  echo "  Likely cause: python3 in the NIM image is a symlink to /usr/bin (not copied in older images)." >&2
  echo "  Fix: rebuild ContentLocalization with scripts/docker/copy-nim-bundle.sh (see Dockerfile)." >&2
  echo "  Check on this pod:" >&2
  echo "    find ${bundle_root} -path '*/dist-packages/nimlib' -type d" >&2
  echo "    ls -la ${bundle_root}/usr/local/bin/python3 ${bundle_root}/usr/bin/python3 2>/dev/null" >&2
  exit 1
fi
chmod +x "${start_server}" 2>/dev/null || true

# start_server.sh execs /usr/local/bin/start_server (absolute). Run nimlib with the bundled
# NIM interpreter so packages and native extensions match the nvcr.io image.
if [[ "${start_server}" == */usr/local/bin/start_server ]]; then
  server_argv=("${nim_python}" "${start_server}")
elif [[ "${start_server}" == *.sh ]]; then
  server_argv=("${nim_python}" "-m" "nimlib.start_server")
else
  server_argv=("${nim_python}" "${start_server}")
fi

# Official NIM images use WORKDIR /opt/nim; keep relative paths in start_server working.
if [[ -d "${bundle_root}/opt/nim" ]]; then
  cd "${bundle_root}/opt/nim"
fi

echo "Starting bundled ${nim_type} NIM: ${entrypoint} ${server_argv[*]}"
echo "  NIM_CACHE_PATH=${NIM_CACHE_PATH}"
echo "  NIM_CACHE_DIR=${NIM_CACHE_DIR}"
echo "  NIM_PYTHON=${nim_python} ($("${nim_python}" --version 2>&1 | head -1))"
echo "  PYTHONPATH=${PYTHONPATH:-}"
echo "  NGC_API_KEY set: $([ -n "${NGC_API_KEY:-}" ] && echo yes || echo NO)"
echo "  NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-unset}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi -L || true
fi
exec "${entrypoint}" "${server_argv[@]}"
