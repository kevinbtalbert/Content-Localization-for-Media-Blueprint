#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Start the full Content Localization stack inside a single container:
#   NIM sidecars (Docker) → S2S → Controller → Demo UI

set -euo pipefail

if [[ -f /home/cdsw/pyproject.toml ]]; then
  APP_ROOT=/home/cdsw
else
  APP_ROOT="${APP_ROOT:-/opt/content-localization}"
fi

export APP_ROOT
cd "$APP_ROOT"

# Load blueprint defaults when a config file is provided
CONFIG_FILE="${CONFIG_FILE:-${APP_ROOT}/configs/elevenlabs.env}"
if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    export "$line"
  done < "$CONFIG_FILE"
  set +a
fi

export PYTHONPATH="${APP_ROOT}:${APP_ROOT}/src:${APP_ROOT}/client:${APP_ROOT}/protos/generated:${PYTHONPATH:-}"
PYTHON="${APP_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

export S2S_SERVER="${S2S_SERVER:-127.0.0.1:${S2S_GRPC_API_PORT:-50050}}"
export LIPSYNC_SERVER="${LIPSYNC_SERVER:-127.0.0.1:${LIPSYNC_NIM_GRPC_API_PORT:-50054}}"
export ASD_SERVER="${ASD_SERVER:-127.0.0.1:${ASD_GRPC_API_PORT:-50055}}"
export CONTROLLER_SERVER="${CONTROLLER_SERVER:-127.0.0.1:${CONTROLLER_GRPC_API_PORT:-50056}}"

START_NIMS="${START_NIMS:-1}"
if [[ "$START_NIMS" == "1" ]] && command -v docker >/dev/null; then
  bash "${APP_ROOT}/scripts/docker/start-nims.sh"
else
  echo "Skipping NIM startup (START_NIMS=${START_NIMS})"
fi

S2S_MODE="el_dubbing"
if [[ "${S2S_SERVICE:-EL_DUBBING}" == "CAMB_DUBBING" ]]; then
  S2S_MODE="camb_dubbing"
fi

echo "Starting S2S (${S2S_MODE})..."
"$PYTHON" "${APP_ROOT}/src/s2s_service/entrypoint.py" "$S2S_MODE" \
  --service-uri "$S2S_SERVER" \
  --max-concurrency "${S2S_MAX_CONCURRENCY:-1}" \
  --concurrency-mode "${S2S_GRPC_CONCURRENCY_MODE:-threading}" \
  --threads-per-process "${S2S_GRPC_THREADS_PER_PROCESS:-1}" \
  --sample-rate-hz "${S2S_SAMPLE_RATE_HZ:-16000}" \
  --message-size "${S2S_MESSAGE_SIZE:-67108864}" \
  --default-source-language "${S2S_DEFAULT_SOURCE_LANGUAGE:-auto}" \
  --default-target-language "${S2S_DEFAULT_TARGET_LANGUAGE:-de}" \
  --audio-format MP3 &
S2S_PID=$!

"${APP_ROOT}/scripts/docker/wait-for-grpc.sh" "${S2S_GRPC_API_PORT:-50050}" 120

echo "Starting Controller..."
CONTROLLER_ARGS=(
  "$PYTHON" "${APP_ROOT}/src/controller_service/entrypoint.py"
  --service-uri "$CONTROLLER_SERVER"
  --max-concurrency "${CONTROLLER_MAX_CONCURRENCY:-1}"
  --concurrency-mode "${CONTROLLER_GRPC_CONCURRENCY_MODE:-threading}"
  --threads-per-process "${CONTROLLER_GRPC_THREADS_PER_PROCESS:-1}"
  --s2s-server "$S2S_SERVER"
  --lipsync-server "$LIPSYNC_SERVER"
  --asd-server "$ASD_SERVER"
)
"${CONTROLLER_ARGS[@]}" &
CTRL_PID=$!

"${APP_ROOT}/scripts/docker/wait-for-grpc.sh" "${CONTROLLER_GRPC_API_PORT:-50056}" 180

UI_PORT="${CDSW_APP_PORT:-${APP_PORT:-${PORT:-3000}}}"
export PORT="$UI_PORT"
export NODE_ENV="${NODE_ENV:-production}"
export OUTPUT_DIR="${OUTPUT_DIR:-/var/lib/content-localization/demo-app}"
export INPUT_DIR="${INPUT_DIR:-${APP_ROOT}/assets}"
mkdir -p "$OUTPUT_DIR"

echo "Starting Demo UI on port ${UI_PORT}..."
cd "${APP_ROOT}/client/demos"
exec npm run start
