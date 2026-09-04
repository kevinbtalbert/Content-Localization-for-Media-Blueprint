#!/usr/bin/env bash
# Bake Maxine NIM model weights into a directory (used inside a NIM image stage or on the host).
#
# LipSync/ASD do not expose LLM-style ``download-to-cache``; weights are pulled when the
# NIM entrypoint starts. This script starts the entrypoint, waits until the cache grows,
# then stops the process.
#
# Requires: NGC_API_KEY, network, and ideally a GPU (TensorRT engines may compile on first start).
set -euo pipefail

nim_type="${1:?lipsync or asd}"
cache_dir="${NIM_CACHE_DIR:-/opt/nim/.cache}"
max_wait_s="${NIM_BAKE_TIMEOUT_S:-7200}"
min_bytes="${NIM_BAKE_MIN_BYTES:-1048576}"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: NGC_API_KEY must be set to bake ${nim_type} model weights." >&2
  exit 1
fi

mkdir -p "${cache_dir}"

entrypoint=""
for candidate in \
  /opt/nvidia/nvidia_entrypoint.sh \
  /opt/nvidia-nim/${nim_type}/opt/nvidia/nvidia_entrypoint.sh; do
  if [[ -x "${candidate}" ]]; then
    entrypoint="${candidate}"
    break
  fi
done
if [[ -z "${entrypoint}" ]]; then
  entrypoint="$(find /opt/nvidia-nim/"${nim_type}" /opt -name 'nvidia_entrypoint.sh' -type f 2>/dev/null | head -1 || true)"
fi
if [[ -z "${entrypoint}" || ! -f "${entrypoint}" ]]; then
  echo "ERROR: could not locate nvidia_entrypoint.sh for ${nim_type}" >&2
  exit 1
fi

if "${entrypoint}" download-to-cache >/dev/null 2>&1; then
  echo "[${nim_type}] download-to-cache completed"
  du -sh "${cache_dir}"
  exit 0
fi

http_port="${NIM_HTTP_API_PORT:-19900}"
grpc_port="${NIM_GRPC_API_PORT:-19901}"
export NIM_HTTP_API_PORT="${http_port}"
export NIM_GRPC_API_PORT="${grpc_port}"
export NIM_CACHE_DIR="${cache_dir}"
export NIM_CACHE_PATH="${cache_dir}"

echo "[${nim_type}] Starting entrypoint to pull model weights into ${cache_dir} ..."
echo "[${nim_type}] entrypoint=${entrypoint}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi -L || true
else
  echo "[${nim_type}] WARNING: no GPU visible — bake may fail or hang for Maxine NIMs" >&2
fi

"${entrypoint}" &
ep_pid=$!
trap 'kill "${ep_pid}" 2>/dev/null || true' EXIT

deadline=$((SECONDS + max_wait_s))
last_bytes=0
stable_passes=0

while (( SECONDS < deadline )); do
  bytes="$(du -sb "${cache_dir}" 2>/dev/null | awk '{print $1}' || echo 0)"
  if curl -sf "http://127.0.0.1:${http_port}/v1/health/ready" >/dev/null 2>&1; then
    echo "[${nim_type}] NIM health ready; cache $(du -sh "${cache_dir}" | awk '{print $1}')"
    break
  fi
  if (( bytes >= min_bytes )); then
    if (( bytes == last_bytes )); then
      stable_passes=$((stable_passes + 1))
      if (( stable_passes >= 12 )); then
        echo "[${nim_type}] Cache size stable at $(du -sh "${cache_dir}" | awk '{print $1}')"
        break
      fi
    else
      stable_passes=0
    fi
    echo "[${nim_type}] Cache growing: $(du -sh "${cache_dir}" | awk '{print $1}')"
  fi
  last_bytes="${bytes}"
  sleep 10
done

kill "${ep_pid}" 2>/dev/null || true
wait "${ep_pid}" 2>/dev/null || true
trap - EXIT

final_bytes="$(du -sb "${cache_dir}" 2>/dev/null | awk '{print $1}' || echo 0)"
if (( final_bytes < min_bytes )); then
  echo "ERROR: ${nim_type} model cache bake failed — ${cache_dir} is still empty/small (${final_bytes} bytes)." >&2
  echo "Ensure NGC_API_KEY has AI for Media access and run on a GPU host." >&2
  exit 1
fi

echo "[${nim_type}] Baked $(du -sh "${cache_dir}" | awk '{print $1}') into ${cache_dir}"
