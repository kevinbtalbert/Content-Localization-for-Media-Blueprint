#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${CDSW_PROJECT_DIR:-/home/cdsw}"
RAY_ROOT="$PROJECT_ROOT/cai/ray"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

cd "$RAY_ROOT"
echo "Launching Ray cluster from $RAY_ROOT"
exec "$VENV_PYTHON" cai_integration/launch_ray_cluster.py "$@"
