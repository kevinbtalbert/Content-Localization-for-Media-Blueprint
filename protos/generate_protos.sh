#!/bin/bash
set -euo pipefail

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# Get the directory where this script is located (portable version)
SCRIPT_DIR="$(dirname "$0")"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to the repo root directory
cd "$REPO_ROOT"

# Verify grpc_tools is importable before generating anything
if ! python -c "import grpc_tools.protoc" 2>/dev/null; then
    echo "ERROR: grpc_tools is not installed." >&2
    echo "Activate the venv and install dependencies first:" >&2
    echo "  source .venv/bin/activate" >&2
    echo "  uv pip install -r pyproject.toml" >&2
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p protos/generated

# Generate gRPC code for all proto files together
echo "Compiling all proto files..."
python -m grpc_tools.protoc \
    --proto_path=protos \
    --python_out=protos/generated \
    --pyi_out=protos/generated \
    --grpc_python_out=protos/generated \
    protos/health.proto \
    protos/nvidia/ai4m/s2s/v1/s2s.proto \
    protos/nvidia/ai4m/common/v1/common.proto \
    protos/nvidia/ai4m/audio/v1/audio.proto \
    protos/nvidia/ai4m/video/v1/video.proto \
    protos/nvidia/ai4m/activespeakerdetection/v1/activespeakerdetection.proto \
    protos/nvidia/ai4m/lipsync/v1/lipsync.proto \
    protos/nvidia/ai4m/controller/v1/controller.proto

# Add __init__.py files to all generated directories
echo "Adding __init__.py files to generated directories..."
find protos/generated -type d -exec touch {}/__init__.py \;

echo "Generated gRPC code in $REPO_ROOT/protos/generated"
ls -ltr protos/generated
