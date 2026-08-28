#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Container entrypoint for the unified Content Localization image.
#   stack  — full pipeline (default for docker compose / docker run)
#   shell  — interactive shell (CAI Workbench sessions)
#   exec   — run an arbitrary command

set -euo pipefail

MODE="${1:-stack}"
shift || true

if [[ -f /home/cdsw/pyproject.toml ]]; then
  APP_ROOT=/home/cdsw
else
  APP_ROOT="${APP_ROOT:-/opt/content-localization}"
fi
export APP_ROOT
export PATH="/opt/content-localization/.venv/bin:${PATH}:/usr/local/bin"

case "$MODE" in
  stack)
    exec bash "${APP_ROOT}/scripts/docker/start-stack.sh" "$@"
    ;;
  shell|bash)
    exec /bin/bash "$@"
    ;;
  exec)
    exec "$@"
    ;;
  *)
    exec "$MODE" "$@"
    ;;
esac
