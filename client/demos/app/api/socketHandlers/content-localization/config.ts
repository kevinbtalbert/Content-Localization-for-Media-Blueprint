/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import path from "path";

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
  const projectRoot = process.env.CDSW_PROJECT_DIR || "/home/cdsw";
  const endpointsPath = path.join(projectRoot, "cai/config/runtime_endpoints.env");
  if (fs.existsSync(endpointsPath)) {
    for (const line of fs.readFileSync(endpointsPath, "utf8").split("\n")) {
      const trimmed = line.trim();
      if (trimmed.startsWith("CONTROLLER_SERVER=")) {
        const value = trimmed.split("=", 2)[1]?.trim().replace(/^"|"$/g, "");
        if (value) {
          return value;
        }
      }
    }
  }
  const controllerMeta = path.join(projectRoot, "cai/config/controller_endpoint.json");
  if (fs.existsSync(controllerMeta)) {
    try {
      const meta = JSON.parse(fs.readFileSync(controllerMeta, "utf8")) as {
        host?: string;
        port?: number;
        grpc_address?: string;
      };
      if (meta.grpc_address) {
        return meta.grpc_address;
      }
      if (meta.host && meta.port) {
        return `${meta.host}:${meta.port}`;
      }
    } catch {
      // fall through to env default
    }
  }
  return process.env.CONTROLLER_SERVER || "localhost:50056";
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
