#!/bin/bash
# shellcheck disable=SC1091
# Content Localization CAI runtime startup helpers

export CONTENT_LOCALIZATION_CAI_HOME="${CONTENT_LOCALIZATION_CAI_HOME:-/home/cdsw/cai}"

ngc_login() {
  if [[ -z "${NGC_API_KEY:-}" ]]; then
    echo "NGC_API_KEY is not set"
    return 1
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
