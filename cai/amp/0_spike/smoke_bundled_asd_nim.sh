#!/usr/bin/env bash
# Smoke test bundled ASD NIM in a GPU Workbench session (ContentLocalization 1.9.0+).
#
#   git pull && bash cai/amp/0_spike/smoke_bundled_asd_nim.sh
#
# Options:
#   --check-only   Preflight only — no server start
#   --timeout SEC  Health wait (default 900)
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
bundle="/opt/nvidia-nim/asd"
launcher="${project}/cai/runtime/scripts/run-bundled-nim.sh"
log="${project}/cai/config/smoke_asd_nim.log"
http_port="${NIM_HTTP_API_PORT:-8005}"
grpc_port="${NIM_GRPC_API_PORT:-50055}"
timeout_s=900
check_only=0
nim_pid=""

usage() {
  sed -n '2,9p' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only) check_only=1; shift ;;
    --timeout) timeout_s="${2:?seconds}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

cleanup() {
  if [[ -n "${nim_pid}" ]] && kill -0 "${nim_pid}" 2>/dev/null; then
    echo
    echo "Stopping smoke-test NIM (pid ${nim_pid}) ..."
    kill "${nim_pid}" 2>/dev/null || true
    wait "${nim_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

step() { echo; echo "=== $* ==="; }

step "Environment"
echo "Project:  ${project}"
echo "Pod IP:   ${CDSW_IP_ADDRESS:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
nvidia-smi -L 2>/dev/null || echo "  (nvidia-smi unavailable — use a GPU session)"
echo "/dev/shm: $(df -h /dev/shm 2>/dev/null | awk 'NR==2 {print $2 " total, " $4 " avail"}' || echo unknown)"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: NGC_API_KEY is not set." >&2
  exit 1
fi

step "Bundle + launcher"
if [[ ! -f "${bundle}/entrypoint" ]]; then
  echo "ERROR: ASD bundle missing at ${bundle}." >&2
  exit 1
fi
if [[ ! -f "${launcher}" ]]; then
  launcher="/usr/local/bin/run-bundled-nim"
fi
chmod +x "${launcher}" 2>/dev/null || true

for fix in link_bundle_tritonserver prepare-bundled-nim-models NIM_DISABLE_GRPC_STARTUP; do
  if ! grep -q "${fix}" "${launcher}"; then
    echo "ERROR: launcher missing ${fix} — git pull origin main" >&2
    exit 1
  fi
done

if [[ ! -f "${bundle}/opt/ai4m/active-speaker-detection/grpc/run_grpc_service.sh" \
   || ! -d "${bundle}/opt/ai4m/active-speaker-detection/models" ]]; then
  echo "ERROR: bundled ASD service paths missing (opt/ai4m)." >&2
  exit 1
fi
if [[ ! -d "${bundle}/opt/tritonserver/backends" ]]; then
  echo "ERROR: opt/tritonserver missing in ASD bundle — rebuild runtime 1.9.0+." >&2
  exit 1
fi
echo "Launcher + ai4m service paths: OK"

baked="/opt/nvidia-nim/baked-model-cache/asd"
cache="${project}/volumes/models/asd-smoke"
mkdir -p "${cache}"
if [[ -d "${baked}" ]] && [[ -n "$(ls -A "${baked}" 2>/dev/null)" ]]; then
  if [[ "$(du -sb "${cache}" 2>/dev/null | awk '{print $1}')" -lt "$(du -sb "${baked}" 2>/dev/null | awk '{print $1}')" ]]; then
    echo "Seeding smoke cache from baked weights ..."
    rm -rf "${cache:?}/"* "${cache:?}/".* 2>/dev/null || true
    cp -a "${baked}/." "${cache}/"
  fi
fi
echo "Smoke cache: $(du -sh "${cache}" 2>/dev/null | awk '{print $1}') at ${cache}"

if (( check_only )); then
  echo "PASS: preflight OK (--check-only)"
  exit 0
fi

grpc_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -lnt | grep -q ":${port} "
    return
  fi
  python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', ${port})); s.close()" 2>/dev/null
}

step "Start bundled ASD NIM (background)"
mkdir -p "$(dirname "${log}")"
: >"${log}"

python3 - <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))
from cai.lib.nim_runtime import configure_asd_env

configure_asd_env()
PY
# shellcheck source=/dev/null
source "${project}/cai/config/asd_nim.env"
export NIM_CACHE_PATH="${cache}"

echo "Log: ${log}"
echo "Waiting for HTTP :${http_port} and gRPC :${grpc_port} (timeout ${timeout_s}s) ..."
"${launcher}" asd >>"${log}" 2>&1 &
nim_pid=$!

deadline=$((SECONDS + timeout_s))
while (( SECONDS < deadline )); do
  if ! kill -0 "${nim_pid}" 2>/dev/null; then
    echo "ERROR: NIM exited early. Log tail:" >&2
    tail -40 "${log}" >&2 || true
    exit 1
  fi
  http_ok=0 grpc_ok=0
  curl -sf "http://127.0.0.1:${http_port}/v1/health/ready" >/dev/null 2>&1 && http_ok=1
  grpc_listening "${grpc_port}" && grpc_ok=1
  if (( http_ok && grpc_ok )); then
    step "PASS"
    echo "ASD NIM ready on HTTP :${http_port} and gRPC :${grpc_port}"
    tail -25 "${log}"
    nim_pid=""
    exit 0
  fi
  if (( (SECONDS % 30) == 0 )); then
    echo "[$(date -Iseconds)] waiting ... HTTP=${http_ok} gRPC=${grpc_ok}"
    tail -3 "${log}" 2>/dev/null | sed 's/^/  | /' || true
  fi
  sleep 5
done

echo "ERROR: timed out waiting for HTTP :${http_port} and gRPC :${grpc_port}" >&2
tail -40 "${log}" >&2 || true
exit 1
