#!/usr/bin/env bash
# Copy a NIM container rootfs into an isolated bundle prefix for CAI exec mode.
# Follows symlinks for usr/local/bin and usr/bin/python* so python3 works outside
# the original container (python3 is often usr/local/bin/python3 -> /usr/bin/python3.12).
set -euo pipefail

src="${1:?source root (e.g. /nim-src)}"
dest="${2:?bundle dest (e.g. /opt/nvidia-nim/lipsync)}"
record_script="${3:-/tmp/record-nim-bundle-entrypoint.sh}"

src="${src%/}"
dest="${dest%/}"

copy_tree() {
  local rel="$1"
  if [[ -e "${src}/${rel}" ]]; then
    mkdir -p "${dest}/$(dirname "${rel}")"
    cp -a "${src}/${rel}" "${dest}/${rel}"
  fi
}

mkdir -p "${dest}"

for rel in \
  opt/nim \
  opt/nvidia \
  opt/tritonserver \
  usr/local/lib \
  usr/local/lib64 \
  usr/lib \
  usr/lib64 \
  lib \
  lib64; do
  copy_tree "${rel}"
done

# Python deps (wrapt, etc.) are often symlinks into paths outside copied trees — dereference site dirs.
copy_python_site() {
  local rel
  for rel in \
    usr/local/lib/python3.12/dist-packages \
    usr/local/lib/python3.11/dist-packages \
    usr/local/lib/python3.10/dist-packages \
    usr/local/lib/python3.12/site-packages \
    usr/lib/python3.12/dist-packages \
    usr/lib/python3/dist-packages; do
    if [[ -d "${src}/${rel}" ]]; then
      mkdir -p "${dest}/${rel}"
      cp -aL "${src}/${rel}/." "${dest}/${rel}/" 2>/dev/null || cp -a "${src}/${rel}/." "${dest}/${rel}/"
    fi
  done
}
copy_python_site

mkdir -p "${dest}/usr/local/bin" "${dest}/usr/bin"
if [[ -d "${src}/usr/local/bin" ]]; then
  # Preserve tree first; some NIM images have broken symlinks (ncu, nsys) that break cp -aL on the whole dir.
  cp -a "${src}/usr/local/bin/." "${dest}/usr/local/bin/" 2>/dev/null || true
  for bin in python3 python3.12 python3.11 python3.10 python start_server; do
    if [[ -e "${src}/usr/local/bin/${bin}" ]]; then
      cp -aL "${src}/usr/local/bin/${bin}" "${dest}/usr/local/bin/${bin}" 2>/dev/null || true
    fi
  done
fi
for py in python3 python3.12 python3.11 python3.10 python; do
  if [[ -e "${src}/usr/bin/${py}" ]]; then
    cp -aL "${src}/usr/bin/${py}" "${dest}/usr/bin/${py}" 2>/dev/null || true
  fi
done

if ! find "${dest}" -path '*/dist-packages/nimlib' -type d 2>/dev/null | grep -q .; then
  echo "ERROR: nimlib not found under ${dest} after NIM bundle copy." >&2
  echo "  Check nvcr.io NIM image layout or expand copy-nim-bundle.sh paths." >&2
  exit 1
fi

if ! find "${dest}" \( -path '*/usr/local/bin/python3*' -o -path '*/usr/bin/python3*' \) -type f 2>/dev/null | grep -q .; then
  echo "ERROR: no python3 binary found under ${dest} after NIM bundle copy." >&2
  exit 1
fi

# Fail the image build if nimlib cannot be imported with the bundled interpreter.
py="$(find "${dest}" \( -path '*/usr/bin/python3*' -o -path '*/usr/local/bin/python3*' \) -type f 2>/dev/null | head -1)"
nimlib_dir="$(find "${dest}" -path '*/dist-packages/nimlib' -type d 2>/dev/null | head -1)"
site="$(dirname "${nimlib_dir}")"
dali_wheel="${dest}/opt/tritonserver/backends/dali/wheel/dali"
bundle_pythonpath="${dali_wheel}:${site}:${dest}/opt/nim"
export LD_LIBRARY_PATH="${dest}/usr/local/lib:${dest}/usr/local/lib64:${dest}/usr/lib/x86_64-linux-gnu:${dest}/usr/lib:${dest}/lib/x86_64-linux-gnu:${dest}/lib:${LD_LIBRARY_PATH:-}"
if [[ ! -d "${dali_wheel}/wrapt" ]]; then
  echo "ERROR: Triton DALI wheel (wrapt) missing at ${dali_wheel}" >&2
  echo "  Ensure opt/tritonserver is copied from the NIM image." >&2
  exit 1
fi
if ! PYTHONPATH="${site}" "${py}" -c "import nimlib" >/dev/null 2>&1; then
  echo "ERROR: bundled python cannot import nimlib under ${dest}" >&2
  echo "  python=${py}  site=${site}" >&2
  exit 1
fi
echo "nimlib import OK: ${nimlib_dir}/__init__.py"

if ! PYTHONPATH="${bundle_pythonpath}" "${py}" -c "import wrapt" >/dev/null 2>&1; then
  echo "ERROR: bundled python cannot import wrapt under ${dest}" >&2
  echo "  Expected PYTHONPATH to include ${dali_wheel} (NIM sets this via DALI wheel)." >&2
  exit 1
fi
echo "wrapt import OK: ${dali_wheel}/wrapt"

if ! PYTHONPATH="${bundle_pythonpath}" "${py}" -c "from opentelemetry.instrumentation.utils import http_status_to_status_code" >/dev/null 2>&1; then
  echo "ERROR: bundled python cannot import opentelemetry instrumentation deps under ${dest}" >&2
  exit 1
fi
echo "opentelemetry import OK"

manifest="$(find "${dest}/opt/nim" -path '*/etc/model_manifest.yaml' -type f 2>/dev/null | head -1 || true)"
if [[ -z "${manifest}" && ! -f "${dest}/opt/nim/etc/default/model_manifest.yaml" ]]; then
  echo "ERROR: model manifest missing under ${dest}/opt/nim/etc" >&2
  exit 1
fi
echo "model manifest OK: ${manifest:-${dest}/opt/nim/etc/default/model_manifest.yaml}"

if [[ ! -f "${dest}/usr/local/bin/start_server" ]]; then
  echo "ERROR: usr/local/bin/start_server missing under ${dest}" >&2
  exit 1
fi

bash "${record_script}" "${dest}"
