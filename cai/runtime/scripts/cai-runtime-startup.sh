#!/bin/bash
# shellcheck disable=SC1091
# Content Localization CAI runtime startup helpers

export CONTENT_LOCALIZATION_CAI_HOME="${CONTENT_LOCALIZATION_CAI_HOME:-/home/cdsw/cai}"
export APP_ROOT="${APP_ROOT:-/opt/content-localization}"
export PATH="/usr/local/bin:/usr/bin:/bin:${APP_ROOT}/scripts/docker:${PATH:-}"

ngc_login() {
  if [[ -z "${NGC_API_KEY:-}" ]]; then
    echo "NGC_API_KEY is not set"
    return 1
  fi
  if [[ ! -S /var/run/docker.sock ]]; then
    echo "Skipping docker login (no Docker socket — CAI uses platform image pull for NIM apps)"
    return 0
  fi
  echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin
}

content-localization-status() {
  echo "CAI home: $CONTENT_LOCALIZATION_CAI_HOME"
  echo "Ray head: ${RAY_HEAD_APP_NAME:-content-localization-ray-head}"
  if [[ -f /home/cdsw/cai/config/runtime_endpoints.env ]]; then
    cat /home/cdsw/cai/config/runtime_endpoints.env
  fi
}
