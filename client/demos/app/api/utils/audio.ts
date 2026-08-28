/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

const DEFAULT_CHUNK_SIZE = 4096;

/**
 * Creates a generator for audio and video chunks
 * @param audioBuffer - The audio buffer
 * @param videoBuffer - The video buffer
 * @param audioChunkSize - The size of the audio chunks
 * @param videoChunkSize - The size of the video chunks
 * @returns An array of audio and video chunks
 */
export function createAudioVideoChunkGenerator(
  audioBuffer: Buffer,
  videoBuffer: Buffer,
  audioChunkSize: number = DEFAULT_CHUNK_SIZE,
  videoChunkSize: number = 64 * 1024, // 64KB chunks like the Python version
): { audio_data: Uint8Array; video_file_data: Uint8Array; request_id: string }[] {
  const audioChunks: Buffer[] = [];
  for (let i = 0; i < audioBuffer.length; i += audioChunkSize) {
    audioChunks.push(audioBuffer.subarray(i, i + audioChunkSize));
  }

  const videoChunks: Buffer[] = [];
  for (let i = 0; i < videoBuffer.length; i += videoChunkSize) {
    videoChunks.push(videoBuffer.subarray(i, i + videoChunkSize));
  }

  // Use the longer array to determine how many chunks to create
  const maxLength = Math.max(audioChunks.length, videoChunks.length);
  const chunks: any[] = [];

  for (let i = 0; i < maxLength; i++) {
    const audioChunk = i < audioChunks.length ? audioChunks[i] : null;
    const videoChunk = i < videoChunks.length ? videoChunks[i] : null;

    chunks.push({
      audio_data: audioChunk ? new Uint8Array(audioChunk) : undefined,
      video_file_data: videoChunk ? new Uint8Array(videoChunk) : undefined,
      request_id: `req-${i}`,
    });
  }

  return chunks;
}
