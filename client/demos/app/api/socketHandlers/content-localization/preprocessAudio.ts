/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import path from "path";
import logger from "../../../utils/logger";
import { processAudioWithAdvancedSettings } from "../../utils/audioProcessing";

export interface PreprocessAudioParams {
  streamId: string;
  audioChunks: Buffer[];
  voiceIsolation: boolean;
  customDiarizationFile: Buffer | null;
  audioOutputDir: string;
  diarizationOutputDir: string;
  sourceLanguage?: string;
}

export interface ProcessedAudioResult {
  audioFilePath?: string;
  /** Set when diarization succeeded; undefined or null when skipped or unavailable. */
  diarizationFilePath?: string | null;
  /** Non-fatal warning from a preprocessing step (e.g. voice isolation or diarization failed). */
  warning?: string;
}

/**
 * Preprocesses audio end-to-end: writes chunks to a WAV file, finalizes it,
 * then runs voice isolation and/or diarization. Chunks are already Buffer (decode once at WS entry).
 */
export async function preprocessAudioEndToEnd(params: PreprocessAudioParams): Promise<ProcessedAudioResult> {
  const {
    streamId,
    audioChunks,
    voiceIsolation,
    customDiarizationFile,
    audioOutputDir,
    diarizationOutputDir,
    sourceLanguage,
  } = params;

  if (audioChunks.length === 0) {
    logger.warn("[ContentLocalization] Preprocess: no audio chunks, skipping file write");
    return {
      audioFilePath: undefined,
      diarizationFilePath: undefined,
    };
  }

  const outputAudioFilePath = path.join(audioOutputDir, `${streamId}.wav`);
  const outputAudioFileStream = fs.createWriteStream(outputAudioFilePath);

  for (const chunk of audioChunks) {
    if (chunk.length > 0) {
      outputAudioFileStream.write(chunk);
    }
  }

  await new Promise<void>((resolve, reject) => {
    outputAudioFileStream.on("finish", () => {
      logger.info("[ContentLocalization] Preprocess: audio file written", { path: outputAudioFilePath });
      resolve();
    });
    outputAudioFileStream.on("error", reject);
    outputAudioFileStream.end();
  });

  return processAudioWithAdvancedSettings({
    streamId,
    audioFilePath: outputAudioFilePath,
    voiceIsolation,
    customDiarizationFile,
    audioOutputDir,
    diarizationOutputDir,
    sourceLanguage,
  });
}

/**
 * Reads a processed audio file and splits it into N Buffer chunks (same count
 * as original stream chunks) for sending to the controller. Returns Buffers
 * to avoid base64 encode/decode round-trip.
 */
export function readProcessedAudioAsChunks(audioFilePath: string, numChunks: number): Buffer[] {
  if (numChunks <= 0 || !fs.existsSync(audioFilePath)) {
    return [];
  }
  const buffer = fs.readFileSync(audioFilePath);
  const chunkSize = Math.ceil(buffer.length / numChunks);
  const chunks: Buffer[] = [];
  for (let i = 0; i < numChunks; i++) {
    const start = i * chunkSize;
    const end = i === numChunks - 1 ? buffer.length : (i + 1) * chunkSize;
    chunks.push(Buffer.from(buffer.subarray(start, end)));
  }
  return chunks;
}
