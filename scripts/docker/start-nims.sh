#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Start LipSync and ASD NIM containers sharing the parent container network
# namespace so all services communicate via 127.0.0.1.

set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/content-localization}"
cd "$APP_ROOT"

NGC_KEY="${NGC_API_KEY:-${LIPSYNC_API_KEY:-${ASD_API_KEY:-}}}"
if [[ -z "$NGC_KEY" ]]; then
  echo "ERROR: Set NGC_API_KEY (or LIPSYNC_API_KEY / ASD_API_KEY) to pull NIM images." >&2
  exit 1
fi

NETWORK_MODE="container:$(cat /etc/hostname)"
LIPSYNC_IMAGE="${LIPSYNC_IMAGE:-nvcr.io/nim/nvidia/lipsync:1.3.0}"
ASD_IMAGE="${ASD_IMAGE:-nvcr.io/nim/nvidia/active-speaker-detection:1.1.0}"
LIPSYNC_HTTP="${LIPSYNC_NIM_HTTP_API_PORT:-8004}"
LIPSYNC_GRPC="${LIPSYNC_NIM_GRPC_API_PORT:-50054}"
ASD_HTTP="${ASD_NIM_HTTP_API_PORT:-8005}"
ASD_GRPC="${ASD_GRPC_API_PORT:-50055}"
LIPSYNC_CACHE="${LIPSYNC_MODEL_MOUNT_PATH:-/var/lib/content-localization/models/lipsync}"
ASD_CACHE="${ASD_MODEL_MOUNT_PATH:-/var/lib/content-localization/models/asd}"
LIPSYNC_TAGS="${LIPSYNC_NIM_TAGS_SELECTOR:-language=de}"

mkdir -p "$LIPSYNC_CACHE" "$ASD_CACHE"

LIPSYNC_GPU="${NIM_LIPSYNC_GPU:-0}"
ASD_GPU="${NIM_ASD_GPU:-1}"

echo "Starting LipSync NIM ($LIPSYNC_IMAGE) on GPU ${LIPSYNC_GPU}..."
docker rm -f cl-lipsync 2>/dev/null || true
docker run -d --name cl-lipsync \
  --network "$NETWORK_MODE" \
  --runtime=nvidia \
  --gpus "device=${LIPSYNC_GPU}" \
  --shm-size=4g \
  -e "NGC_API_KEY=${NGC_KEY}" \
  -e "NIM_HTTP_API_PORT=${LIPSYNC_HTTP}" \
  -e "NIM_GRPC_API_PORT=${LIPSYNC_GRPC}" \
  -e "NIM_TAGS_SELECTOR=${LIPSYNC_TAGS}" \
  -e "NIM_MAX_CONCURRENCY_PER_GPU=1" \
  -e "LIPSYNC_DEBUG_MODE=${LIPSYNC_DEBUG_MODE:-0}" \
  -v "${LIPSYNC_CACHE}:/opt/nim/.cache:rw" \
  "$LIPSYNC_IMAGE"

echo "Starting ASD NIM ($ASD_IMAGE) on GPU ${ASD_GPU}..."
docker rm -f cl-asd 2>/dev/null || true
docker run -d --name cl-asd \
  --network "$NETWORK_MODE" \
  --runtime=nvidia \
  --gpus "device=${ASD_GPU}" \
  --shm-size=4g \
  -e "NGC_API_KEY=${NGC_KEY}" \
  -e "NIM_HTTP_API_PORT=${ASD_HTTP}" \
  -e "NIM_GRPC_API_PORT=${ASD_GRPC}" \
  -e "MAXINE_MAX_CONCURRENCY_PER_GPU=1" \
  -v "${ASD_CACHE}:/opt/nim/.cache:rw" \
  "$ASD_IMAGE"

echo "Waiting for NIM health endpoints..."
"${APP_ROOT}/scripts/docker/wait-for-url.sh" "http://127.0.0.1:${LIPSYNC_HTTP}/v1/health/ready" 900
"${APP_ROOT}/scripts/docker/wait-for-url.sh" "http://127.0.0.1:${ASD_HTTP}/v1/health/ready" 900
echo "NIM containers are ready."
