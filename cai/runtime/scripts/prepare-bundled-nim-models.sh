#!/usr/bin/env bash
# Populate NVCF model mount paths from NGC cache snapshots before Maxine/Triton starts.
# LipSync/ASD inference expects:
#   /opt/nim/workspace/config/models/<name>  (workspace engines)
#   /config/models/<name>                  (symlink target for Triton model repo version dirs)
set -euo pipefail

nim_type="${1:?lipsync or asd}"
cache="${2:-${NIM_CACHE_PATH:-}}"

if [[ -z "${cache}" || ! -d "${cache}" ]]; then
  exit 0
fi

case "${nim_type}" in
  lipsync)
    ws="/opt/nim/workspace/config/models/lipsync"
    mount="/config/models/lipsync"
    hub="models--nim--nvidia--lipsync"
    ;;
  asd)
    ws="/opt/nim/workspace/config/models/active-speaker-detection"
    mount="/config/models/active-speaker-detection"
    hub="models--nim--nvidia--active-speaker-detection"
    ;;
  *)
    echo "ERROR: unknown nim_type '${nim_type}'" >&2
    exit 1
    ;;
esac

mkdir -p "${ws}" /config/models

link_engines_from_dir() {
  local src="$1"
  local f bn
  [[ -d "${src}" ]] || return 0
  shopt -s nullglob
  for f in "${src}"/*.trtpkg; do
    bn="$(basename "${f}")"
    if [[ ! -e "${ws}/${bn}" ]]; then
      ln -sfn "${f}" "${ws}/${bn}"
    fi
  done
  shopt -u nullglob
}

snap=""
while IFS= read -r candidate; do
  if compgen -G "${candidate}"/*.trtpkg >/dev/null 2>&1; then
    snap="${candidate}"
    break
  fi
done < <(find "${cache}" -type d -path "*/${hub}/snapshots/*" 2>/dev/null | sort -r)

if [[ -n "${snap}" ]]; then
  link_engines_from_dir "${snap}"
fi

# Materialization may place engines elsewhere under workspace.
while IFS= read -r f; do
  [[ -e "${f}" ]] || continue
  bn="$(basename "${f}")"
  if [[ ! -e "${ws}/${bn}" ]]; then
    ln -sfn "${f}" "${ws}/${bn}"
  fi
done < <(find /opt/nim/workspace -name '*.trtpkg' \( -type f -o -type l \) 2>/dev/null)

if [[ -d "${ws}" ]]; then
  if [[ -e "${mount}" && ! -L "${mount}" ]]; then
    rm -rf "${mount}"
  fi
  ln -sfn "${ws}" "${mount}"
fi
