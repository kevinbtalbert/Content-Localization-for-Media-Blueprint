/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

/// <reference lib="dom" />

"use client";

import logger from "./logger";

export type CodecId = "default" | "fallback";

/**
 * Codec configuration for streaming and download
 */
export const CODEC_CONFIG = {
  streaming: {
    default: "video/mp4; codecs=avc1.42E01E, opus",
    fallback: "video/webm; codecs=vp9, opus",
  },
  download: {
    default: "video/mp4; codecs=avc1.42E01E, mp3",
    fallback: "video/webm; codecs=vp9, opus",
  },
} as const;

/**
 * Detects the best supported codec ID for MediaSource streaming
 */
export function detectStreamingCodecId(): CodecId {
  // Check if we're in a browser environment
  if (
    typeof window === "undefined" ||
    typeof MediaSource === "undefined" ||
    typeof MediaSource.isTypeSupported !== "function"
  ) {
    logger.warn("MediaSource API not available, using fallback codec");
    return "fallback";
  }

  try {
    const isDefaultSupported = MediaSource.isTypeSupported(CODEC_CONFIG.streaming.default);
    const codecId: CodecId = isDefaultSupported ? "default" : "fallback";
    return codecId;
  } catch (error) {
    logger.warn("Error detecting streaming codec:", error);
    return "fallback";
  }
}

/**
 * Detects the best supported codec ID for video element playback
 */
export function detectDownloadCodecId(): CodecId {
  // Check if we're in a browser environment
  if (typeof window === "undefined" || typeof document === "undefined") {
    logger.warn("Browser environment not available, using fallback codec");
    return "fallback";
  }

  try {
    const video = document.createElement("video");
    const canPlayDefault = video.canPlayType(CODEC_CONFIG.download.default);
    const codecId: CodecId = canPlayDefault !== "" ? "default" : "fallback";
    video.remove();

    return codecId;
  } catch (error) {
    logger.warn("Error detecting download codec:", error);
    return "fallback";
  }
}

/**
 * Gets the codec string for a given type and ID
 */
export function getCodecString(type: "streaming" | "download", codecId: CodecId): string {
  return CODEC_CONFIG[type][codecId];
}

/**
 * Gets the file extension for a given codec ID
 */
export function getFileExtension(codecId: CodecId): string {
  return codecId === "default" ? "mp4" : "webm";
}
