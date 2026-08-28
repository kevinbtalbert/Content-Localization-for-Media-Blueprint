# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

#!/bin/sh
echo "Compiling all proto files..."

CURRENT_DIR="$(pwd)"

BASE_REPO_DIR="$(cd ../.. && pwd)"

echo "BASE_REPO_DIR: $BASE_REPO_DIR"
echo "CURRENT_DIR: $CURRENT_DIR"
echo "PROTO_PATH: $BASE_REPO_DIR/protos/nvidia/ai4m/controller/v1/controller.proto"

# Create the output directory if it doesn't exist
mkdir -p $CURRENT_DIR/app/generated_protos

protoc \
    --plugin=$CURRENT_DIR/node_modules/.bin/protoc-gen-ts_proto \
    --proto_path=$BASE_REPO_DIR/protos \
    --ts_proto_out=$CURRENT_DIR/app/generated_protos \
    --ts_proto_opt=esModuleInterop=true,outputServices=grpc-js,snakeToCamel=false \
    $BASE_REPO_DIR/protos/nvidia/ai4m/controller/v1/controller.proto 

ls -ltr $CURRENT_DIR/app/generated_protos
