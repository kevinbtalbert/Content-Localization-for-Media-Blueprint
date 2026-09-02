#!/usr/bin/env bash
# CAI application launcher: load endpoints, start app-port probe, exec Controller gRPC.
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
cd "${project}"

python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))
from cai.lib.cai_common import apply_dotenv_to_os, write_dotenv_file
from cai.lib.paths import ENDPOINTS_ENV
from cai.lib.service_env import configure_python_env, load_config_defaults

configure_python_env()
load_config_defaults()
apply_dotenv_to_os(ENDPOINTS_ENV)

host = os.environ.get("CDSW_IP_ADDRESS", "127.0.0.1")
port = os.environ.get("CONTROLLER_GRPC_API_PORT", "50056")
controller_endpoint = f"{host}:{port}"

endpoints = apply_dotenv_to_os(ENDPOINTS_ENV) if ENDPOINTS_ENV.exists() else {}
endpoints["CONTROLLER_SERVER"] = controller_endpoint
write_dotenv_file(ENDPOINTS_ENV, endpoints)

meta = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw")) / "cai" / "config" / "controller_endpoint.json"
meta.parent.mkdir(parents=True, exist_ok=True)
meta.write_text(
    json.dumps({"host": host, "port": int(port), "grpc_address": controller_endpoint}, indent=2) + "\n"
)
print(f"Controller endpoint metadata: {meta}", flush=True)
print(f"Controller gRPC will listen on {controller_endpoint}", flush=True)
PY

app_port="${CDSW_APP_PORT:-8100}"
sidecar_log="${project}/cai/config/controller_sidecar.log"
nohup python3 "${project}/cai/amp/4_services/run_cai_app_port.py" \
  --port "${app_port}" \
  --service-label controller \
  >>"${sidecar_log}" 2>&1 &
echo "Started CAI app port probe on ${app_port} (log: ${sidecar_log})"

python="${project}/.venv/bin/python"
if [[ ! -x "${python}" ]]; then
  python="$(command -v python3)"
fi

# shellcheck source=/dev/null
source "${project}/cai/config/runtime_endpoints.env" 2>/dev/null || true

exec "${python}" "${project}/src/controller_service/entrypoint.py" \
  --service-uri "${CDSW_IP_ADDRESS:-127.0.0.1}:${CONTROLLER_GRPC_API_PORT:-50056}" \
  --max-concurrency "${CONTROLLER_MAX_CONCURRENCY:-1}" \
  --concurrency-mode "${CONTROLLER_GRPC_CONCURRENCY_MODE:-threading}" \
  --threads-per-process "${CONTROLLER_GRPC_THREADS_PER_PROCESS:-1}" \
  --s2s-server "${S2S_SERVER:?S2S_SERVER must be set — run Wire Service Endpoints first}" \
  --lipsync-server "${LIPSYNC_SERVER:?LIPSYNC_SERVER must be set — run Wire Service Endpoints first}" \
  --lipsync-ssl-mode "${CONTROLLER_LIPSYNC_SSL_MODE:-DISABLED}" \
  --asd-ssl-mode "${CONTROLLER_ASD_SSL_MODE:-DISABLED}" \
  ${ASD_SERVER:+--asd-server "${ASD_SERVER}"}
