#!/usr/bin/env bash
# Record the NIM server entrypoint inside a bundled prefix (image build step).
set -euo pipefail

bundle_root="${1:?bundle root}"
entrypoint_file="${bundle_root}/entrypoint"

if [[ -f "${bundle_root}/opt/nvidia/nvidia_entrypoint.sh" ]]; then
  printf '%s\n' "${bundle_root}/opt/nvidia/nvidia_entrypoint.sh" >"${entrypoint_file}"
  # Wrapper must pass start_server.sh — nvidia_entrypoint.sh alone execs bash and exits.
  if [[ -f "${bundle_root}/opt/nim/start_server.sh" ]]; then
    printf '%s\n' "${bundle_root}/opt/nim/start_server.sh" >"${bundle_root}/start_server"
  fi
  exit 0
fi

found="$(find "${bundle_root}" -name 'nvidia_entrypoint.sh' -type f 2>/dev/null | head -1 || true)"
if [[ -n "${found}" ]]; then
  printf '%s\n' "${found}" >"${entrypoint_file}"
  exit 0
fi

found="$(find "${bundle_root}" -path '*/opt/nim/*' -name 'start*.sh' -type f 2>/dev/null | head -1 || true)"
if [[ -n "${found}" ]]; then
  printf '%s\n' "${found}" >"${entrypoint_file}"
  exit 0
fi

echo "ERROR: could not locate NIM entrypoint under ${bundle_root}" >&2
exit 1
