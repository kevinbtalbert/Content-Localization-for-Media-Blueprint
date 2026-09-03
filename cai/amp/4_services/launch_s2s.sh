#!/usr/bin/env bash
# CAI application launcher: write S2S metadata, start app-port probe, exec gRPC service.
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
cd "${project}"

host="${CDSW_IP_ADDRESS:-127.0.0.1}"
port="${S2S_GRPC_API_PORT:-50050}"
export S2S_SERVER="${host}:${port}"

python3 - <<PY
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))
from cai.lib.service_env import load_config_defaults, require_generated_protos, write_service_launcher_env

require_generated_protos()
write_service_launcher_env()
load_config_defaults()

project = Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))
endpoint_file = project / "cai" / "config" / "s2s_endpoint.json"
endpoint_file.parent.mkdir(parents=True, exist_ok=True)
host = os.environ.get("CDSW_IP_ADDRESS", "127.0.0.1")
endpoint_file.write_text(
    json.dumps(
        {
            "host": host,
            "port": int(os.environ.get("S2S_GRPC_API_PORT", "50050")),
            "grpc_address": os.environ.get("S2S_SERVER", f"{host}:{os.environ.get('S2S_GRPC_API_PORT', '50050')}"),
        },
        indent=2,
    )
    + "\n"
)
print(f"S2S endpoint metadata: {endpoint_file}", flush=True)
print(f"S2S gRPC will listen on {os.environ['S2S_SERVER']}", flush=True)
PY

app_port="${CDSW_APP_PORT:-8100}"
sidecar_log="${project}/cai/config/s2s_sidecar.log"
nohup python3 "${project}/cai/amp/4_services/run_cai_app_port.py" \
  --port "${app_port}" \
  --service-label s2s \
  >>"${sidecar_log}" 2>&1 &
echo "Started CAI app port probe on ${app_port} (log: ${sidecar_log})"

# shellcheck source=/dev/null
source "${project}/cai/config/service_launcher.env"

python="${project}/.venv/bin/python"
if [[ ! -x "${python}" ]]; then
  python="$(command -v python3)"
fi

service="${S2S_SERVICE:-EL_DUBBING}"
subcommand="camb_dubbing"
if [[ "${service}" != "CAMB_DUBBING" ]]; then
  subcommand="el_dubbing"
fi

exec "${python}" "${project}/src/s2s_service/entrypoint.py" \
  "${subcommand}" \
  --service-uri "${S2S_SERVER}" \
  --max-concurrency "${S2S_MAX_CONCURRENCY:-1}" \
  --concurrency-mode "${S2S_GRPC_CONCURRENCY_MODE:-threading}" \
  --threads-per-process "${S2S_GRPC_THREADS_PER_PROCESS:-1}" \
  --sample-rate-hz "${S2S_SAMPLE_RATE_HZ:-16000}" \
  --message-size "${S2S_MESSAGE_SIZE:-67108864}" \
  --default-source-language "${S2S_DEFAULT_SOURCE_LANGUAGE:-auto}" \
  --default-target-language "${S2S_DEFAULT_TARGET_LANGUAGE:-de}" \
  --audio-format MP3
