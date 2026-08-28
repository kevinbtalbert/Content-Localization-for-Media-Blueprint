/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { CodecId } from "../../utils/codecConfig";

/**
 * FFmpeg configuration for streaming with real-time encoding
 */
const STREAMING_CONFIG = {
  default: [
    "-i",
    "pipe:0",
    "-c:v",
    "copy", // Copy video codec (no re-encoding)
    "-c:a",
    "libopus", // Opus audio codec
    "-movflags",
    "frag_keyframe+empty_moov+default_base_moof", // Fragmented MP4 for streaming
    "-f",
    "mp4",
    "-vsync",
    "passthrough", // Preserve original frame timestamps
    "pipe:1",
  ],
  fallback: [
    "-i",
    "pipe:0",
    "-c:v",
    "libvpx-vp9", // VP9 video codec
    "-crf",
    "30", // Quality level (lower = better quality)
    "-b:v",
    "0", // Variable bitrate mode
    "-deadline",
    "realtime", // Fastest encoding for real-time streaming
    "-cpu-used",
    "8", // Speed/quality trade-off (higher = faster)
    "-c:a",
    "libopus", // Opus audio codec
    "-b:a",
    "128k", // Audio bitrate
    "-f",
    "webm",
    "-vsync",
    "passthrough", // Preserve original frame timestamps
    "-cluster_size_limit",
    "2M", // Limit cluster size for better streaming
    "-cluster_time_limit",
    "5100", // ~5 second clusters
    "pipe:1",
  ],
} as const;

/**
 * Gets FFmpeg arguments for streaming based on codec ID
 */
export function getStreamingArgs(codecId: CodecId): readonly string[] {
  return STREAMING_CONFIG[codecId];
}

/**
 * Gets FFmpeg arguments for remuxing for fallback codec
 */
export function getFallbackRemuxArgs(inputPath: string, outputPath: string): readonly string[] {
  return [
    "-y",
    "-i",
    inputPath,
    "-c:v",
    "libvpx-vp9", // VP9 video codec
    "-crf",
    "30", // Quality level
    "-b:v",
    "0", // Variable bitrate mode
    "-deadline",
    "good", // Good quality/speed tradeoff
    "-cpu-used",
    "2", // Speed/quality trade-off
    "-c:a",
    "libopus", // Opus audio codec
    "-vsync",
    "passthrough", // Preserve original frame timestamps
    "-b:a",
    "128k", // Audio bitrate
    "-f",
    "webm",
    outputPath,
  ];
}
