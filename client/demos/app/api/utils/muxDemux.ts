/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { spawn } from "child_process";
import logger from "../../utils/logger";
import * as fs from "fs";
import { getFallbackRemuxArgs } from "./ffmpegConfig";
import type { CodecId } from "../../utils/codecConfig";

/**
 * Remuxes/re-encodes video file using FFmpeg
 * @param inputPath - Path to input video file
 * @param outputPath - Path to output video file
 * @param codecId - Codec ID to use for encoding
 */
export const remuxVideo = async (inputPath: string, outputPath: string, codecId: CodecId): Promise<void> => {
  return new Promise<void>(async (resolve, reject) => {
    // For default codec, just copy the file without re-encoding
    if (codecId === "default") {
      logger.info("Using default codec, copying file without re-encoding");
      try {
        fs.copyFileSync(inputPath, outputPath);
        resolve();
      } catch (error) {
        logger.error("Error copying file:", error);
        reject(error);
      }
      return;
    }

    // For fallback codec, remux with FFmpeg
    const ffmpegProcess = spawn("ffmpeg", getFallbackRemuxArgs(inputPath, outputPath));

    ffmpegProcess.stderr.on("data", (data: Buffer) => {
      logger.info(`ffmpeg: ${data.toString()}`);
    });

    ffmpegProcess.on("close", (code: number) => {
      if (code === 0) {
        logger.info(`Remuxed video written to ${outputPath}`);
        resolve();
      } else {
        logger.error(`Error remuxing video: ffmpeg exited with code ${code}`);
        reject(new Error(`ffmpeg exited with code ${code}`));
      }
    });

    ffmpegProcess.on("error", (err: Error) => {
      logger.error("Error spawning ffmpeg process:", err);
      reject(err);
    });
  });
};
