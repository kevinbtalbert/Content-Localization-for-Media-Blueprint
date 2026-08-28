#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

PORT="${1:?gRPC port required}"
TIMEOUT="${2:-300}"
APP_ROOT="${APP_ROOT:-/opt/content-localization}"

deadline=$((SECONDS + TIMEOUT))
until grpcurl -plaintext \
  -import-path "${APP_ROOT}/protos" \
  -proto "${APP_ROOT}/protos/health.proto" \
  "127.0.0.1:${PORT}" grpc.health.v1.Health/Check >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for gRPC health on port ${PORT}" >&2
    exit 1
  fi
  sleep 3
done
echo "gRPC healthy on port ${PORT}"
