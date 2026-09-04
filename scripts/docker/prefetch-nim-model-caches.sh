#!/usr/bin/env bash
# Prefetch LipSync + ASD model weights on the build host, then stage them for docker build.
#
# Run BEFORE ``docker build`` (or use scripts/docker/build-content-localization-image.sh).
# Uses ``docker run`` on the build machine (with GPU) — not inside CAI.
#
# Required:
#   export NGC_API_KEY=...
#
# Optional:
#   LIPSYNC_NIM_TAGS_SELECTOR=language=de   (default; one language per bake)
#   NIM_PREFETCH_GPU=all                    (default) or device=0, device=1, ...
#
# See build/nim-model-cache/README.md for GPU support, sizes, and arch tagging.
#
# Output: build/nim-model-cache/{lipsync,asd}/  → copied into the ContentLocalization image.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${root}"

# shellcheck source=scripts/docker/nim-gpu-arch.sh
source "${root}/scripts/docker/nim-gpu-arch.sh"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: export NGC_API_KEY before prefetch (same key as: docker login nvcr.io)." >&2
  exit 1
fi

LIPSYNC_IMAGE="${LIPSYNC_IMAGE:-nvcr.io/nim/nvidia/lipsync:1.3.0}"
ASD_IMAGE="${ASD_IMAGE:-nvcr.io/nim/nvidia/active-speaker-detection:1.1.0}"
LIPSYNC_TAGS="${LIPSYNC_NIM_TAGS_SELECTOR:-language=de}"
NIM_PREFETCH_GPU="${NIM_PREFETCH_GPU:-all}"
OUT_ROOT="${root}/build/nim-model-cache"
WORK="${root}/build/nim-prefetch-work"
TIMEOUT_S="${NIM_PREFETCH_TIMEOUT_S:-7200}"
MIN_BYTES=1048576
# Minimum staged cache after /v1/health/ready (override if your language profile is smaller).
LIPSYNC_MIN_CACHE_BYTES="${NIM_PREFETCH_MIN_BYTES_LIPSYNC:-$((3 * 1024 * 1024 * 1024))}"
ASD_MIN_CACHE_BYTES="${NIM_PREFETCH_MIN_BYTES_ASD:-$((2 * 1024 * 1024 * 1024))}"

print_prefetch_plan() {
  echo "=== NIM model prefetch plan ==="
  echo "  LipSync image:     ${LIPSYNC_IMAGE}"
  echo "  ASD image:         ${ASD_IMAGE}"
  echo "  LipSync language:  ${LIPSYNC_TAGS}"
  echo "  Docker GPU flag:   --gpus ${NIM_PREFETCH_GPU}"
  echo "  Output:            ${OUT_ROOT}/{lipsync,asd}"
  echo "  Expected cache:    ~6–10 GB LipSync + ~4–8 GB ASD (see README for totals)"
  echo "  Success criteria:  /v1/health/ready + minimum cache size (no early exit on flat du)"
  echo

  nim_validate_prefetch_gpu "${NIM_PREFETCH_GPU}" || exit 1

  if [[ "${NIM_PREFETCH_GPU_ARCH:-unknown}" != "unknown" ]]; then
    echo "Image will be tagged: content-localization:1.5.0-${NIM_PREFETCH_GPU_ARCH} (via build script)"
    echo
  fi
}

print_prefetch_plan

mkdir -p "${OUT_ROOT}/lipsync" "${OUT_ROOT}/asd" "${WORK}/lipsync" "${WORK}/asd"

prefetch_one() {
  local name="$1"
  local image="$2"
  local out_dir="$3"
  local work_dir="$4"
  local host_http="$5"
  local container="$6"
  local min_ready_bytes="$7"
  shift 7
  local -a extra_env=("$@")

  echo "=== Prefetch ${name} (${image}) ==="
  echo "  Requires /v1/health/ready and cache >= $(numfmt --to=iec-i --suffix=B "${min_ready_bytes}" 2>/dev/null || echo "${min_ready_bytes} bytes")"
  rm -rf "${work_dir:?}/"*
  mkdir -p "${work_dir}"
  chmod 777 "${work_dir}"
  docker rm -f "${container}" 2>/dev/null || true

  local -a run_cmd=(
    docker run -d
    --name "${container}"
    --runtime=nvidia
    --gpus "${NIM_PREFETCH_GPU}"
    --shm-size=8g
    --ipc=host
    -e "NGC_API_KEY=${NGC_API_KEY}"
    -e NIM_CACHE_DIR=/opt/nim/.cache
    -e NIM_HTTP_API_PORT=18080
    -e NIM_GRPC_API_PORT=18081
    -e NIM_MAX_CONCURRENCY_PER_GPU=1
    -p "${host_http}:18080"
    -v "${work_dir}:/opt/nim/.cache:rw"
  )
  run_cmd+=("${extra_env[@]}")
  run_cmd+=("${image}")

  echo "Starting ${container} ..."
  "${run_cmd[@]}" >/dev/null

  local deadline=$((SECONDS + TIMEOUT_S))
  local last_bytes=0
  local ready=0
  while (( SECONDS < deadline )); do
    if ! docker inspect -f '{{.State.Running}}' "${container}" 2>/dev/null | grep -q true; then
      echo "ERROR: ${container} exited early. Logs:" >&2
      docker logs "${container}" 2>&1 | tail -40 >&2 || true
      docker rm -f "${container}" 2>/dev/null || true
      exit 1
    fi

    local bytes
    bytes="$(du -sb "${work_dir}" 2>/dev/null | awk '{print $1}' || echo 0)"
    local health_ok=0
    if curl -sf "http://127.0.0.1:${host_http}/v1/health/ready" >/dev/null 2>&1; then
      health_ok=1
    fi
    if (( health_ok && bytes >= min_ready_bytes )); then
      ready=1
      echo "${name}: health ready ($(du -sh "${work_dir}" | awk '{print $1}'))"
      break
    fi
    if (( health_ok && bytes >= MIN_BYTES )); then
      echo "${name}: health ready at $(du -sh "${work_dir}" | awk '{print $1}') — waiting for cache >= $(numfmt --to=iec-i --suffix=B "${min_ready_bytes}" 2>/dev/null || echo "${min_ready_bytes} bytes") ..."
    elif (( bytes != last_bytes && bytes >= MIN_BYTES )); then
      echo "${name}: cache growing $(du -sh "${work_dir}" | awk '{print $1}') (waiting for /v1/health/ready) ..."
    fi
    last_bytes="${bytes}"
    sleep 10
  done

  if (( ! ready )); then
    echo "ERROR: ${name} prefetch timed out after ${TIMEOUT_S}s — /v1/health/ready never succeeded." >&2
    echo "  Cache size: $(du -sh "${work_dir}" 2>/dev/null | awk '{print $1}' || echo 0)" >&2
    echo "  Partial caches are not baked into the image. Check NGC key, GPU, and container logs." >&2
    docker logs "${container}" 2>&1 | tail -60 >&2 || true
  fi

  docker stop "${container}" >/dev/null 2>&1 || true
  docker wait "${container}" >/dev/null 2>&1 || true
  docker rm -f "${container}" >/dev/null 2>&1 || true

  local final_bytes
  final_bytes="$(du -sb "${work_dir}" 2>/dev/null | awk '{print $1}' || echo 0)"
  if (( ! ready )); then
    exit 1
  fi
  if (( final_bytes < min_ready_bytes )); then
    echo "ERROR: ${name} reported health ready but cache is too small (${final_bytes} bytes < ${min_ready_bytes})." >&2
    echo "  Likely incomplete download — refusing to stage a partial bake." >&2
    exit 1
  fi
  if (( final_bytes < MIN_BYTES )); then
    echo "ERROR: ${name} prefetch failed — ${work_dir} is empty (${final_bytes} bytes)." >&2
    exit 1
  fi

  rm -rf "${out_dir:?}/"*
  cp -a "${work_dir}/." "${out_dir}/"
  echo "${name}: staged $(du -sh "${out_dir}" | awk '{print $1}') → ${out_dir}"
}

prefetch_one lipsync "${LIPSYNC_IMAGE}" "${OUT_ROOT}/lipsync" "${WORK}/lipsync" 18080 \
  prefetch-lipsync "${LIPSYNC_MIN_CACHE_BYTES}" -e "NIM_TAGS_SELECTOR=${LIPSYNC_TAGS}"

prefetch_one asd "${ASD_IMAGE}" "${OUT_ROOT}/asd" "${WORK}/asd" 18082 \
  prefetch-asd "${ASD_MIN_CACHE_BYTES}" -e MAXINE_MAX_CONCURRENCY_PER_GPU=1

nim_write_build_metadata "${OUT_ROOT}" "${NIM_PREFETCH_GPU}" "${LIPSYNC_TAGS}"

lipsync_gb="$(du -sh "${OUT_ROOT}/lipsync" | awk '{print $1}')"
asd_gb="$(du -sh "${OUT_ROOT}/asd" | awk '{print $1}')"
total_gb="$(du -sh "${OUT_ROOT}" | awk '{print $1}')"
arch="$(nim_read_gpu_arch "${OUT_ROOT}" "${NIM_PREFETCH_GPU}")"

echo
echo "=== Prefetch sizes ==="
echo "  LipSync: ${lipsync_gb}"
echo "  ASD:     ${asd_gb}"
echo "  Total:   ${total_gb}  (+ ~25 GB NIM binaries/runtime → expect ~35–45 GB final image)"
echo "  GPU arch: ${arch}"
echo
echo "Prefetch complete. Build the runtime image with:"
echo "  ./scripts/docker/build-content-localization-image.sh"
echo "  → tag: content-localization:1.5.0-${arch}"
