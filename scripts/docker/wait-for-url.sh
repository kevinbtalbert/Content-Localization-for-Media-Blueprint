#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

URL="${1:?URL required}"
TIMEOUT="${2:-600}"
INTERVAL="${3:-5}"

deadline=$((SECONDS + TIMEOUT))
until curl -fsS "$URL" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "Timed out waiting for $URL" >&2
    exit 1
  fi
  sleep "$INTERVAL"
done
echo "OK: $URL"
