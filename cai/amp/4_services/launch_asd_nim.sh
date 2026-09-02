#!/usr/bin/env bash
# CAI application launcher: configure env, start sidecar, exec NIM.
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
cd "${project}"

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
    "First start may take 15–120+ minutes while NIM downloads model weights from NGC.",
    flush=True,
)
PY

# shellcheck source=/dev/null
source "${project}/cai/config/asd_nim.env"
unset ASD_MODEL_MOUNT_PATH

app_port="${CDSW_APP_PORT:-8100}"
sidecar_log="${project}/cai/config/asd_sidecar.log"
nohup python3 "${project}/cai/amp/4_services/run_nim_sidecar.py" \
  --nim-type asd \
  --name asd-nim \
  --grpc-port "${NIM_GRPC_API_PORT}" \
  --http-port "${NIM_HTTP_API_PORT}" \
  --cache-dir "${NIM_CACHE_DIR}" \
  --app-port "${app_port}" \
  >>"${sidecar_log}" 2>&1 &
echo "Started NIM sidecar (app port ${app_port}, logs: ${sidecar_log})"

(
  cache="${NIM_CACHE_DIR}"
  while true; do
    if [[ -d "${cache}" ]]; then
      size="$(du -sh "${cache}" 2>/dev/null | awk '{print $1}')"
      echo "[$(date -Iseconds)] Model cache ${cache}: ${size} (growing until NIM reports ready)"
    fi
    sleep 120
  done
) &

launcher="${project}/cai/runtime/scripts/run-bundled-nim.sh"
if [[ ! -f "${launcher}" ]]; then
  launcher="/usr/local/bin/run-bundled-nim"
fi
chmod +x "${launcher}" 2>/dev/null || true
exec "${launcher}" asd
