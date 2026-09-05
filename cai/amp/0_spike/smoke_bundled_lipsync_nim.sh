#!/usr/bin/env bash
# Smoke test bundled LipSync NIM in a GPU Workbench session (ContentLocalization 1.9.0+).
#
# Confirms the launcher fix before redeploying GPU applications:
#   git pull && bash cai/amp/0_spike/smoke_bundled_lipsync_nim.sh
#
# Options:
#   --check-only   Preflight only (bundle, python, nimlib, launcher) — no server start
#   --timeout SEC  Health wait (default 900)
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
bundle="/opt/nvidia-nim/lipsync"
launcher="${project}/cai/runtime/scripts/run-bundled-nim.sh"
log="${project}/cai/config/smoke_lipsync_nim.log"
http_port="${NIM_HTTP_API_PORT:-8004}"
grpc_port="${NIM_GRPC_API_PORT:-50054}"
timeout_s=900
check_only=0
nim_pid=""

usage() {
  sed -n '2,10p' "$0"
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
echo "Runtime:  ${ML_RUNTIME_EDITION:-?} ${ML_RUNTIME_SHORT_VERSION:-?}.${ML_RUNTIME_MAINTENANCE_VERSION:-?}"
echo "Pod IP:   ${CDSW_IP_ADDRESS:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
echo "GPU:"
nvidia-smi -L 2>/dev/null || echo "  (nvidia-smi unavailable — use a GPU session)"
echo "/dev/shm: $(df -h /dev/shm 2>/dev/null | awk 'NR==2 {print $2 " total, " $4 " avail"}' || echo unknown)"

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: NGC_API_KEY is not set (Project Settings → Environment)." >&2
  exit 1
fi
echo "NGC_API_KEY: set"

step "Bundle + launcher"
if [[ ! -f "${bundle}/entrypoint" ]]; then
  echo "ERROR: LipSync bundle missing at ${bundle} — register ContentLocalization 1.8 runtime." >&2
  exit 1
fi
if [[ ! -f "${launcher}" ]]; then
  launcher="/usr/local/bin/run-bundled-nim"
fi
if [[ ! -f "${launcher}" ]]; then
  echo "ERROR: run-bundled-nim.sh not found in project or image." >&2
  exit 1
fi
chmod +x "${launcher}" 2>/dev/null || true
echo "Bundle entrypoint: $(tr -d '\n' <"${bundle}/entrypoint")"
echo "Launcher:          ${launcher}"

if ! grep -q 'link_bundle_opt_nim_layout' "${launcher}"; then
  echo "ERROR: launcher is missing /opt/nim layout link fix." >&2
  echo "  Run: git pull origin main" >&2
  exit 1
fi
if ! grep -q '/opt/nim/\.bundled_nim_launch_' "${launcher}"; then
  echo "ERROR: launcher is missing the /opt/nim launch wrapper fix." >&2
  echo "  Run: git pull origin main" >&2
  exit 1
fi
if ! grep -q 'NIM_DISABLE_GRPC_STARTUP' "${launcher}"; then
  echo "ERROR: launcher is missing NIM_DISABLE_GRPC_STARTUP (GrpcNIMApiInterface fix)." >&2
  echo "  Run: git pull origin main" >&2
  exit 1
fi
if [[ ! -f "${bundle}/opt/lipsync/grpc/run_grpc_service.sh" || ! -d "${bundle}/opt/maxine/models" ]]; then
  echo "ERROR: bundled LipSync service paths missing (opt/lipsync, opt/maxine)." >&2
  echo "  Rebuild ContentLocalization 1.8+ on a GPU build host, then re-register the runtime." >&2
  exit 1
fi
if ! grep -q 'link_bundle_tritonserver' "${launcher}"; then
  echo "ERROR: launcher is missing /opt/tritonserver link fix." >&2
  echo "  Run: git pull origin main" >&2
  exit 1
fi
prepare="${project}/cai/runtime/scripts/prepare-bundled-nim-models.sh"
if [[ ! -f "${prepare}" ]]; then
  prepare="/usr/local/bin/prepare-bundled-nim-models"
fi
if [[ ! -f "${prepare}" ]]; then
  echo "ERROR: prepare-bundled-nim-models.sh missing." >&2
  exit 1
fi
if [[ ! -d "${bundle}/opt/tritonserver/backends/nv_arsdk_backend" ]]; then
  echo "ERROR: nv_arsdk_backend missing in bundle — rebuild runtime 1.9.0+." >&2
  exit 1
fi
echo "Launcher fixes: present (triton + model paths + NIM image env)"
echo "Service paths: opt/lipsync + opt/maxine present in bundle"

step "Bundled python + nimlib"
py=""
site=""
while IFS= read -r nimlib_dir; do
  site="$(dirname "${nimlib_dir}")"
  while IFS= read -r candidate; do
    [[ -x "${candidate}" ]] || continue
    if PYTHONPATH="${site}" "${candidate}" -c "import nimlib" >/dev/null 2>&1; then
      py="${candidate}"
      break 2
    fi
  done < <(
    find "${bundle}" \
      \( -path '*/usr/bin/python3*' -o -path '*/usr/local/bin/python3*' \) \
      -type f 2>/dev/null | sort -u
  )
done < <(find "${bundle}" -path '*/dist-packages/nimlib' -type d 2>/dev/null | sort -u)

if [[ -z "${py}" ]]; then
  echo "ERROR: bundled python cannot import nimlib under ${bundle}" >&2
  exit 1
fi
echo "NIM python: ${py} ($("${py}" --version 2>&1 | head -1))"
echo "nimlib site: ${site}"
dali_wheel="${bundle}/opt/tritonserver/backends/dali/wheel/dali"
if ! PYTHONNOUSERSITE=1 PYTHONPATH="${dali_wheel}:${site}:/opt/nim" "${py}" -c "import wrapt" >/dev/null 2>&1; then
  echo "ERROR: bundled NIM missing wrapt (need DALI wheel on PYTHONPATH) — rebuild runtime 1.8+." >&2
  exit 1
fi
echo "wrapt: import OK (${dali_wheel})"
if [[ ! -f "${bundle}/opt/nim/etc/model_manifest.yaml" && ! -f "${bundle}/opt/nim/etc/default/model_manifest.yaml" ]]; then
  echo "ERROR: model manifest missing under ${bundle}/opt/nim/etc" >&2
  exit 1
fi
echo "Model manifest: present in bundle"

baked="/opt/nvidia-nim/baked-model-cache/lipsync"
cache="${project}/volumes/models/lipsync-smoke"
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
  echo
  echo "PASS: preflight checks OK (--check-only, NIM not started)."
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

step "Start bundled LipSync NIM (background)"
mkdir -p "$(dirname "${log}")"
: >"${log}"

python3 - <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))
from cai.lib.nim_runtime import configure_lipsync_env

configure_lipsync_env()
PY
# shellcheck source=/dev/null
source "${project}/cai/config/lipsync_nim.env"
export NIM_CACHE_PATH="${cache}"

echo "Log: ${log}"
echo "Waiting for HTTP :${http_port} and gRPC :${grpc_port} (timeout ${timeout_s}s) ..."
"${launcher}" lipsync >>"${log}" 2>&1 &
nim_pid=$!
echo "NIM pid: ${nim_pid}"

deadline=$((SECONDS + timeout_s))
while (( SECONDS < deadline )); do
  if ! kill -0 "${nim_pid}" 2>/dev/null; then
    echo "ERROR: NIM process exited early (pid ${nim_pid}). Log tail:" >&2
    tail -40 "${log}" >&2 || true
    exit 1
  fi
  http_ok=0 grpc_ok=0
  curl -sf "http://127.0.0.1:${http_port}/v1/health/ready" >/dev/null 2>&1 && http_ok=1
  grpc_listening "${grpc_port}" && grpc_ok=1
  if (( http_ok && grpc_ok )); then
    step "PASS"
    echo "LipSync NIM is ready on HTTP :${http_port} and gRPC :${grpc_port}"
    curl -s "http://127.0.0.1:${http_port}/v1/health/ready" || true
    echo
    echo "Recent log:"
    tail -25 "${log}"
    echo
    echo "Safe to redeploy LipSync/ASD GPU applications."
    nim_pid=""
    exit 0
  fi
  if (( (SECONDS % 30) == 0 )); then
    echo "[$(date -Iseconds)] waiting ... HTTP=${http_ok} gRPC=${grpc_ok} cache $(du -sh "${cache}" 2>/dev/null | awk '{print $1}')"
    tail -3 "${log}" 2>/dev/null | sed 's/^/  | /' || true
  fi
  sleep 5
done

echo "ERROR: timed out after ${timeout_s}s waiting for HTTP :${http_port} and gRPC :${grpc_port}" >&2
tail -40 "${log}" >&2 || true
exit 1
