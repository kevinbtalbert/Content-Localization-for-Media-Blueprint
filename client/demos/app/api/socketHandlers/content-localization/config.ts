/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import path from "path";

const SERVER_ADDRESS = process.env.CONTROLLER_SERVER || "localhost:50056";

const OUTPUT_DIR = process.env.OUTPUT_DIR
  ? `${process.env.OUTPUT_DIR}/outputs`
  : path.join(process.cwd(), "public", "outputs");

export const AUDIO_OUTPUT_DIR = path.join(OUTPUT_DIR, "audio");
export const DIARIZATION_OUTPUT_DIR = path.join(OUTPUT_DIR, "diarization");

/** Output directory for localized video files */
export function getOutputDir(): string {
  return OUTPUT_DIR;
}

export function getServerAddress(): string {
  return SERVER_ADDRESS;
}

function ensureDirExists(dirPath: string): void {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

/** Call once at startup so output directories exist */
export function ensureOutputDirs(): void {
  ensureDirExists(OUTPUT_DIR);
  ensureDirExists(AUDIO_OUTPUT_DIR);
  ensureDirExists(DIARIZATION_OUTPUT_DIR);
}
