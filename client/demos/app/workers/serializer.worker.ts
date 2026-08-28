/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

// Web Worker for serializing audio/video chunks to base64 and JSON
// This runs in a separate thread to avoid blocking the UI

self.onmessage = (e: MessageEvent) => {
  const { audio, video, index } = e.data;

  try {
    // Convert ArrayBuffers to base64
    const base64Audio = arrayBufferToBase64(audio);
    const base64Video = video ? arrayBufferToBase64(video) : "";

    // Build and stringify the WebSocket message (offload this work too)
    const message = JSON.stringify({
      type: "data_chunk",
      data: {
        audio: base64Audio,
        video: base64Video,
      },
    });

    // Send stringified message back to main thread
    self.postMessage({
      success: true,
      index,
      message, // Already stringified JSON
    });
  } catch (error) {
    self.postMessage({
      success: false,
      index,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

// Base64 encoding function (same as in your utils)
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

export {};
