#!/usr/bin/env bash
# CAI application launcher (Streamlit AMP pattern): configure env, then exec NIM.
set -euo pipefail

project="${CDSW_PROJECT_DIR:-/home/cdsw}"
cd "${project}"

python3 - <<'PY'
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(os.environ.get("CDSW_PROJECT_DIR", "/home/cdsw"))))
from cai.lib.nim_runtime import configure_asd_env, start_endpoint_publisher

config = configure_asd_env()
print(f"ASD NIM image: {config['source_image']}", flush=True)
print(f"NIM cache dir: {config['cache_dir']}", flush=True)
print(
    f"Listening on gRPC :{config['grpc_port']}, HTTP :{config['http_port']}",
    flush=True,
)
start_endpoint_publisher(
    name=config["name"],
    nim_type=config["nim_type"],
    grpc_port=config["grpc_port"],
    http_port=config["http_port"],
)
PY

# shellcheck source=/dev/null
source "${project}/cai/config/asd_nim.env"
unset ASD_MODEL_MOUNT_PATH

launcher="${project}/cai/runtime/scripts/run-bundled-nim.sh"
if [[ ! -f "${launcher}" ]]; then
  launcher="/usr/local/bin/run-bundled-nim"
fi
chmod +x "${launcher}" 2>/dev/null || true
exec "${launcher}" asd
