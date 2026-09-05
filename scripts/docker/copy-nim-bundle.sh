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

mkdir -p "${dest}/usr/local/bin" "${dest}/usr/bin"
if [[ -d "${src}/usr/local/bin" ]]; then
  cp -aL "${src}/usr/local/bin/." "${dest}/usr/local/bin/"
fi
for py in python3 python3.12 python3.11 python3.10 python; do
  if [[ -e "${src}/usr/bin/${py}" ]]; then
    cp -aL "${src}/usr/bin/${py}" "${dest}/usr/bin/${py}"
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
export LD_LIBRARY_PATH="${dest}/usr/local/lib:${dest}/usr/local/lib64:${dest}/usr/lib/x86_64-linux-gnu:${dest}/usr/lib:${dest}/lib/x86_64-linux-gnu:${dest}/lib:${LD_LIBRARY_PATH:-}"
if ! PYTHONPATH="${site}" "${py}" -c "import nimlib; print('nimlib import OK:', nimlib.__file__)"; then
  echo "ERROR: bundled python cannot import nimlib under ${dest}" >&2
  echo "  python=${py}  site=${site}" >&2
  exit 1
fi

if [[ ! -f "${dest}/usr/local/bin/start_server" ]]; then
  echo "ERROR: usr/local/bin/start_server missing under ${dest}" >&2
  exit 1
fi

bash "${record_script}" "${dest}"
