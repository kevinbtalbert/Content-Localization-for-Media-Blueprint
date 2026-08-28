/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Pipeline status sent over WebSocket for UI progress. Values are serialized as-is.
 */
export enum PIPELINE_STATUS {
  UPLOADING = "uploading",
  PREPROCESSING = "preprocessing",
  LOCALIZING = "localizing",
}
