/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import logger from "../../utils/logger";
import { performDiarization, saveDiarizationFile } from "./elevenlabs";
import { performCambAiDiarization, saveCambAiDiarizationFile } from "./cambai";

/**
 * Save ElevenLabs diarization results.
 * Returns null when diarization is skipped (e.g. API key not set) for graceful degradation.
 *
 * @param streamId - Unique stream identifier
 * @param audioFilePath - Path to the audio file
 * @param outputDir - Directory where diarization files should be saved
 * @returns Promise resolving to the diarization file path, or null if skipped
 */
export async function saveElevenLabsDiarization(
  streamId: string,
  audioFilePath: string,
  outputDir: string,
): Promise<string | null> {
  // Perform diarization
  const response = await performDiarization(audioFilePath, streamId);
  if (!response) {
    logger.warn(`Diarization skipped for stream ${streamId} - no response from ElevenLabs`);
    return null;
  }

  // Save raw diarization data
  const diarizationFilePath = await saveDiarizationFile(streamId, response, outputDir);

  return diarizationFilePath;
}

/**
 * Save Camb AI diarization results.
 * Returns null when diarization is skipped (e.g. API key not set) for graceful degradation.
 *
 * @param streamId - Unique stream identifier
 * @param audioFilePath - Path to the audio file
 * @param outputDir - Directory where diarization files should be saved
 * @param languageId - Camb AI numeric language ID (default: 1 for English)
 * @returns Promise resolving to the diarization file path, or null if skipped
 */
export async function saveCambAiDiarization(
  streamId: string,
  audioFilePath: string,
  outputDir: string,
  languageId: number = 1,
): Promise<string | null> {
  const response = await performCambAiDiarization(audioFilePath, streamId, languageId);
  if (!response) {
    logger.warn(`Diarization skipped for stream ${streamId} - no response from Camb AI`);
    return null;
  }

  const diarizationFilePath = await saveCambAiDiarizationFile(streamId, response, outputDir);
  return diarizationFilePath;
}
