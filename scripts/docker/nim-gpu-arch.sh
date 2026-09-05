#!/usr/bin/env bash
# Shared GPU architecture detection for NIM prefetch / image build.
# Source from other scripts:  source "$(dirname "$0")/nim-gpu-arch.sh"
#
# Writes build/nim-model-cache/.gpu-arch after prefetch (turing, ampere, ada, blackwell, unknown).

nim_gpu_upper() {
  echo "$1" | tr '[:lower:]' '[:upper:]'
}

nim_map_gpu_arch() {
  local name
  name="$(nim_gpu_upper "$1")"
  if [[ "${name}" == *"A100"* || "${name}" == *"H100"* || "${name}" == *"B100"* ]]; then
    echo "unsupported"
  elif [[ "${name}" == *"T4"* || "${name}" == *"TESLA T4"* || "${name}" == *"RTX 20"* ]]; then
    echo "turing"
  elif [[ "${name}" == *"L40"* || "${name}" == *"RTX 40"* || "${name}" == *"RTX 4090"* ]]; then
    echo "ada"
  elif [[ "${name}" == *"B40"* || "${name}" == *"RTX 50"* || "${name}" == *"5080"* || "${name}" == *"5090"* ]]; then
    echo "blackwell"
  elif [[ "${name}" == *"A10"* || "${name}" == *"A16"* || "${name}" == *"A40"* || "${name}" == *" A2"* || "${name}" == *"L4"* ]]; then
    echo "ampere"
  else
    echo "unknown"
  fi
}

# Parse NIM_PREFETCH_GPU (all, device=0, device=0,1) → first device index for arch lookup.
nim_prefetch_gpu_index() {
  local flag="${1:-all}"
  if [[ "${flag}" == "all" ]]; then
    echo 0
    return
  fi
  if [[ "${flag}" == device=* ]]; then
    echo "${flag#device=}" | cut -d, -f1
    return
  fi
  echo 0
}

# Populate NIM_GPU_NAMES and NIM_GPU_ARCHS bash arrays from nvidia-smi.
nim_load_gpu_inventory() {
  NIM_GPU_NAMES=()
  NIM_GPU_ARCHS=()
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 1
  fi
  while IFS= read -r line; do
    [[ -n "${line}" ]] || continue
    NIM_GPU_NAMES+=("${line}")
    NIM_GPU_ARCHS+=("$(nim_map_gpu_arch "${line}")")
  done < <(nvidia-smi --query-gpu=index,gpu_name --format=csv,noheader 2>/dev/null | sed 's/^[0-9]*, //')
  ((${#NIM_GPU_NAMES[@]} > 0))
}

# Set NIM_PREFETCH_GPU_NAME and NIM_PREFETCH_GPU_ARCH for the GPU used during prefetch.
nim_resolve_prefetch_gpu() {
  local gpu_flag="${1:-all}"
  NIM_PREFETCH_GPU_NAME=""
  NIM_PREFETCH_GPU_ARCH="unknown"

  if ! nim_load_gpu_inventory; then
    return 1
  fi

  local idx
  idx="$(nim_prefetch_gpu_index "${gpu_flag}")"
  if (( idx < 0 || idx >= ${#NIM_GPU_NAMES[@]} )); then
    echo "ERROR: NIM_PREFETCH_GPU=${gpu_flag} — no GPU at index ${idx}." >&2
    return 1
  fi

  NIM_PREFETCH_GPU_NAME="${NIM_GPU_NAMES[$idx]}"
  NIM_PREFETCH_GPU_ARCH="${NIM_GPU_ARCHS[$idx]}"
  return 0
}

nim_print_gpu_inventory() {
  local gpu_flag="${1:-all}"
  echo "Build-host GPUs:"
  local i
  for i in "${!NIM_GPU_NAMES[@]}"; do
    local arch="${NIM_GPU_ARCHS[$i]}"
    local note=""
    local marker=" "
    if [[ "${i}" == "$(nim_prefetch_gpu_index "${gpu_flag}")" ]]; then
      marker="*"
    fi
    if [[ "${arch}" == "unsupported" ]]; then
      note=" — NOT supported by LipSync/ASD (no NVENC/NVDEC)"
    fi
    echo "  ${marker}[${i}] ${NIM_GPU_NAMES[$i]} → ${arch}${note}"
  done
  echo "  (* = GPU used for prefetch via NIM_PREFETCH_GPU=${gpu_flag})"
  echo
}

nim_validate_prefetch_gpu() {
  local gpu_flag="${1:-all}"
  if ! nim_resolve_prefetch_gpu "${gpu_flag}"; then
    echo "WARNING: nvidia-smi not available — cannot verify GPU architecture." >&2
    return 0
  fi

  nim_print_gpu_inventory "${gpu_flag}"

  if [[ "${NIM_PREFETCH_GPU_ARCH}" == "unsupported" ]]; then
    echo "ERROR: ${NIM_PREFETCH_GPU_NAME} cannot run Maxine LipSync/ASD. Use T4, L4, A10, L40, etc." >&2
    echo "See build/nim-model-cache/README.md" >&2
    return 1
  fi

  if [[ "${gpu_flag}" == "all" && ${#NIM_GPU_NAMES[@]} -gt 1 ]]; then
    local mixed=0 primary="${NIM_PREFETCH_GPU_ARCH}"
    local arch
    for arch in "${NIM_GPU_ARCHS[@]}"; do
      [[ "${arch}" != "${primary}" && "${arch}" != "unknown" ]] && mixed=1
    done
    if (( mixed )); then
      echo "WARNING: multiple GPU architectures detected. Set NIM_PREFETCH_GPU=device=N" >&2
      echo "         so prefetch uses the same arch as your CAI workers." >&2
      echo
    fi
  fi

  if [[ "${NIM_PREFETCH_GPU_ARCH}" != "unknown" ]]; then
    echo "Prefetch GPU arch: ${NIM_PREFETCH_GPU_ARCH} (${NIM_PREFETCH_GPU_NAME})"
    echo
  fi
  return 0
}

# Persist arch for build-content-localization-image.sh (called after successful prefetch).
nim_write_build_metadata() {
  local meta_dir="$1"
  local gpu_flag="${2:-all}"
  local lipsync_tags="${3:-language=de}"
  mkdir -p "${meta_dir}"
  nim_resolve_prefetch_gpu "${gpu_flag}" || true
  cat > "${meta_dir}/.gpu-arch" <<EOF
${NIM_PREFETCH_GPU_ARCH:-unknown}
EOF
  cat > "${meta_dir}/.build-metadata" <<EOF
GPU_ARCH=${NIM_PREFETCH_GPU_ARCH:-unknown}
GPU_NAME=${NIM_PREFETCH_GPU_NAME:-}
NIM_PREFETCH_GPU=${gpu_flag}
LIPSYNC_NIM_TAGS_SELECTOR=${lipsync_tags}
PREFETCH_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
}

# Read arch written by prefetch; fall back to live nvidia-smi.
nim_read_gpu_arch() {
  local meta_dir="$1"
  local gpu_flag="${2:-all}"
  if [[ -f "${meta_dir}/.gpu-arch" ]]; then
    tr -d '[:space:]' < "${meta_dir}/.gpu-arch"
    return 0
  fi
  if nim_resolve_prefetch_gpu "${gpu_flag}"; then
    echo "${NIM_PREFETCH_GPU_ARCH}"
    return 0
  fi
  echo "unknown"
}

# Compose docker tags: repo:version-arch (+ optional registry mirror).
nim_compose_image_tags() {
  local repo="${1:-content-localization}"
  local version="${2:-1.8.0}"
  local arch="${3:-unknown}"
  local registry="${4:-}"

  local arch_suffix=""
  if [[ "${arch}" != "unknown" ]]; then
    arch_suffix="-${arch}"
  fi

  NIM_IMAGE_TAG_PRIMARY="${repo}:${version}${arch_suffix}"
  NIM_IMAGE_TAGS=("${NIM_IMAGE_TAG_PRIMARY}")

  if [[ -n "${registry}" ]]; then
    NIM_IMAGE_TAGS+=("${registry}:${version}${arch_suffix}")
  fi
}
