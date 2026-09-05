#!/usr/bin/env bash
# CAI application launcher: configure env, start sidecar, exec NIM.
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
cd "${project}"

nim_log="${project}/cai/config/asd_nim.log"
mkdir -p "${project}/cai/config"
exec > >(tee -a "${nim_log}") 2>&1
echo "=== ASD NIM launcher $(date -Iseconds) ==="
echo "Engine type: ${CDSW_ENGINE_TYPE:-unknown}  Pod IP: ${CDSW_IP_ADDRESS:-unknown}"
echo "/dev/shm: $(df -h /dev/shm 2>/dev/null | awk 'NR==2 {print $2 " total, " $4 " avail"}' || echo unknown)"
echo "Application log mirror: ${nim_log}"

if ! nvidia-smi -L >/dev/null 2>&1; then
  echo "ERROR: GPU not visible in this application (nvidia-smi failed)." >&2
  echo "Ensure the app requests 1 GPU and Spark/add-ons are disabled." >&2
  exit 1
fi
nvidia-smi -L || true

python3 - <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))
from cai.lib.nim_runtime import configure_asd_env

config = configure_asd_env()
print(f"ASD NIM image: {config['source_image']}", flush=True)
print(f"NIM cache dir: {config['cache_dir']}", flush=True)
print(
    f"Listening on gRPC :{config['grpc_port']}, HTTP :{config['http_port']}",
    flush=True,
)
print(
    "Model weights come from the runtime image (baked at build) unless cache is empty.",
    flush=True,
)
print(
    "Progress: du -sh volumes/models/asd  |  sidecar: cai/config/asd_sidecar.log",
    flush=True,
)
PY

# shellcheck source=/dev/null
source "${project}/cai/config/asd_nim.env"
unset ASD_MODEL_MOUNT_PATH

if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "ERROR: NGC_API_KEY is empty after sourcing asd_nim.env" >&2
  exit 1
fi

app_port="${CDSW_APP_PORT:-8100}"
sidecar_log="${project}/cai/config/asd_sidecar.log"
nohup python3 "${project}/cai/amp/4_services/run_nim_sidecar.py" \
  --nim-type asd \
  --name asd-nim \
  --grpc-port "${NIM_GRPC_API_PORT}" \
  --http-port "${NIM_HTTP_API_PORT}" \
  --cache-dir "${NIM_CACHE_PATH:-${NIM_CACHE_DIR}}" \
  --app-port "${app_port}" \
  >>"${sidecar_log}" 2>&1 &
echo "Started NIM sidecar (app port ${app_port}, logs: ${sidecar_log})"

(
  cache="${NIM_CACHE_PATH:-${NIM_CACHE_DIR}}"
  grpc_port="${NIM_GRPC_API_PORT:-50055}"
  while true; do
    if [[ -d "${cache}" ]]; then
      size="$(du -sh "${cache}" 2>/dev/null | awk '{print $1}')"
      http_ok=0 grpc_ok=0
      curl -sf "http://127.0.0.1:${NIM_HTTP_API_PORT:-8005}/v1/health/ready" >/dev/null 2>&1 && http_ok=1
      if command -v ss >/dev/null 2>&1; then
        ss -lnt | grep -q ":${grpc_port} " && grpc_ok=1
      elif python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', ${grpc_port})); s.close()" 2>/dev/null; then
        grpc_ok=1
      fi
      if (( http_ok && grpc_ok )); then
        echo "[$(date -Iseconds)] ASD NIM ready on HTTP :${NIM_HTTP_API_PORT:-8005} gRPC :${grpc_port} (cache ${size})"
        break
      fi
      echo "[$(date -Iseconds)] Model cache ${cache}: ${size} (waiting for HTTP :${NIM_HTTP_API_PORT:-8005} + gRPC :${grpc_port})"
    fi
    sleep 120
  done
) &

launcher="${project}/cai/runtime/scripts/run-bundled-nim.sh"
if [[ ! -f "${launcher}" ]]; then
  launcher="/usr/local/bin/run-bundled-nim"
fi
chmod +x "${launcher}" 2>/dev/null || true
echo "Exec bundled NIM launcher: ${launcher} asd"
exec "${launcher}" asd
