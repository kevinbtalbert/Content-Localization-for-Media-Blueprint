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

# nimlib reads /opt/nim/etc/model_manifest.yaml (and LICENSE, etc.). Only .cache was linked before.
link_bundle_opt_nim_layout() {
  local bundle_nim="${bundle_root}/opt/nim"
  local item name target manifest

  if [[ ! -d "${bundle_nim}" ]]; then
    echo "ERROR: bundle opt/nim missing at ${bundle_nim}" >&2
    exit 1
  fi
  if [[ ! -w /opt/nim ]]; then
    echo "ERROR: /opt/nim is not writable — cannot link bundled NIM layout." >&2
    exit 1
  fi

  shopt -s nullglob dotglob
  for item in "${bundle_nim}"/* "${bundle_nim}"/.[!.]* "${bundle_nim}"/..?*; do
    [[ -e "${item}" ]] || continue
    name="$(basename "${item}")"
    [[ "${name}" == ".cache" ]] && continue
    [[ "${name}" == "workspace" ]] && continue
    [[ "${name}" == .bundled_nim_launch_* ]] && continue
    target="/opt/nim/${name}"
    if [[ -e "${target}" && ! -L "${target}" ]]; then
      rm -rf "${target}"
    fi
    ln -sfn "${item}" "${target}"
  done
  shopt -u nullglob dotglob

  manifest="/opt/nim/etc/model_manifest.yaml"
  if [[ ! -f "${manifest}" ]]; then
    manifest="$(find "${bundle_nim}" -path '*/etc/model_manifest.yaml' -type f 2>/dev/null | head -1 || true)"
  fi
  if [[ -z "${manifest}" || ! -f "${manifest}" ]]; then
    manifest="/opt/nim/etc/default/model_manifest.yaml"
  fi
  if [[ ! -f "${manifest}" ]]; then
    echo "ERROR: NIM model manifest not found under ${bundle_nim} or /opt/nim/etc." >&2
    exit 1
  fi
  export NIM_MANIFEST_PATH="${NIM_MANIFEST_PATH:-${manifest}}"
  mkdir -p /opt/nim/workspace
  echo "Linked bundled opt/nim layout into /opt/nim (manifest: ${NIM_MANIFEST_PATH})"
}

configure_nim_runtime_env() {
  case "${nim_type}" in
    lipsync)
      export NIM_HTTP_API_PORT="${NIM_HTTP_API_PORT:-${LIPSYNC_NIM_HTTP_API_PORT:-8004}}"
      export NIM_GRPC_API_PORT="${NIM_GRPC_API_PORT:-${LIPSYNC_NIM_GRPC_API_PORT:-50054}}"
      export NIM_TAGS_SELECTOR="${NIM_TAGS_SELECTOR:-${LIPSYNC_NIM_TAGS_SELECTOR:-language=de}}"
      ;;
    asd)
      export NIM_HTTP_API_PORT="${NIM_HTTP_API_PORT:-${ASD_NIM_HTTP_API_PORT:-8005}}"
      export NIM_GRPC_API_PORT="${NIM_GRPC_API_PORT:-${ASD_GRPC_API_PORT:-50055}}"
      ;;
  esac
  export NIM_MAX_CONCURRENCY_PER_GPU="${NIM_MAX_CONCURRENCY_PER_GPU:-1}"
}

build_nim_pythonpath() {
  local -a parts=()
  local d
  if [[ -n "${nim_site}" ]]; then
    parts+=("${nim_site}")
  fi
  for d in \
    "${bundle_root}/usr/local/lib/python3.12/dist-packages" \
    "${bundle_root}/usr/lib/python3.12/dist-packages" \
    "${bundle_root}/usr/lib/python3/dist-packages" \
    "/opt/nim"; do
    if [[ -d "${d}" ]]; then
      parts+=("${d}")
    fi
  done
  local IFS=:
  echo "${parts[*]}"
}

link_bundle_opt_nim_layout

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
nim_python=""
nim_site=""

resolve_nim_python() {
  local bundle="$1"
  local py site nimlib_dir
  local -a pythons=() nimlib_dirs=()

  nim_python=""
  nim_site=""

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
      # nimlib logs to stdout on import; must not pollute captured output.
      if PYTHONPATH="${site}" "${py}" -c "import nimlib" >/dev/null 2>&1; then
        nim_site="${site}"
        nim_python="${py}"
        export PYTHONPATH="${site}${PYTHONPATH:+:${PYTHONPATH}}"
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
resolve_nim_python "${bundle_root}" || true
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

nim_pythonpath="$(build_nim_pythonpath)"
if ! PYTHONNOUSERSITE=1 PYTHONPATH="${nim_pythonpath}" "${nim_python}" -c "import wrapt; from opentelemetry.instrumentation.utils import http_status_to_status_code" >/dev/null 2>&1; then
  echo "ERROR: bundled NIM Python is missing runtime deps (wrapt/opentelemetry)." >&2
  echo "  Rebuild ContentLocalization 1.6+ with updated copy-nim-bundle.sh (dereference dist-packages)." >&2
  echo "  Quick check: PYTHONPATH=${nim_pythonpath} ${nim_python} -c 'import wrapt'" >&2
  exit 1
fi

configure_nim_runtime_env
nim_ld_library_path="${LD_LIBRARY_PATH:-}"

# nvidia_entrypoint.sh cds to /opt/nim (not the bundle prefix) before exec — wrapper must live there.
launch_wrapper="/opt/nim/.bundled_nim_launch_${nim_type}.sh"
if [[ ! -d /opt/nim ]] || [[ ! -w /opt/nim ]]; then
  echo "ERROR: /opt/nim is not writable — cannot create NIM launch wrapper." >&2
  exit 1
fi
nim_workdir="/opt/nim"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -euo pipefail' \
  'export PYTHONNOUSERSITE=1' \
  "export PYTHONPATH=\"${nim_pythonpath}\"" \
  "export LD_LIBRARY_PATH=\"${nim_ld_library_path}\"" \
  "export NIM_MANIFEST_PATH=\"${NIM_MANIFEST_PATH:-}\"" \
  "export NIM_CACHE_DIR=\"/opt/nim/.cache\"" \
  "export NIM_CACHE_PATH=\"${NIM_CACHE_PATH}\"" \
  "export NIM_HTTP_API_PORT=\"${NIM_HTTP_API_PORT}\"" \
  "export NIM_GRPC_API_PORT=\"${NIM_GRPC_API_PORT}\"" \
  "export NIM_TAGS_SELECTOR=\"${NIM_TAGS_SELECTOR:-}\"" \
  "export NIM_MAX_CONCURRENCY_PER_GPU=\"${NIM_MAX_CONCURRENCY_PER_GPU}\"" \
  "export NGC_API_KEY=\"${NGC_API_KEY:-}\"" \
  "export NVIDIA_VISIBLE_DEVICES=\"${NVIDIA_VISIBLE_DEVICES:-}\"" \
  "cd \"${nim_workdir}\"" \
  "exec \"${nim_python}\" \"${start_server}\"" \
  >"${launch_wrapper}"
chmod +x "${launch_wrapper}"
if [[ ! -x "${launch_wrapper}" ]]; then
  echo "ERROR: failed to create launch wrapper at ${launch_wrapper}" >&2
  exit 1
fi

echo "Starting bundled ${nim_type} NIM: ${entrypoint} ${launch_wrapper}"
echo "  NIM_CACHE_PATH=${NIM_CACHE_PATH}"
echo "  NIM_CACHE_DIR=${NIM_CACHE_DIR}"
echo "  NIM_PYTHON=${nim_python} ($("${nim_python}" --version 2>&1 | head -1))"
echo "  NIM_SITE=${nim_site}"
echo "  START_SERVER=${start_server}"
echo "  LAUNCH_WRAPPER=${launch_wrapper}"
echo "  NIM_MANIFEST_PATH=${NIM_MANIFEST_PATH:-unset}"
echo "  NIM_HTTP_API_PORT=${NIM_HTTP_API_PORT}"
echo "  NIM_GRPC_API_PORT=${NIM_GRPC_API_PORT}"
echo "  NIM_TAGS_SELECTOR=${NIM_TAGS_SELECTOR:-unset}"
echo "  NIM_PYTHONPATH=${nim_pythonpath}"
echo "  PYTHONPATH=${PYTHONPATH:-}"
echo "  NGC_API_KEY set: $([ -n "${NGC_API_KEY:-}" ] && echo yes || echo NO)"
echo "  NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-unset}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi -L || true
fi
exec "${entrypoint}" "${launch_wrapper}"
