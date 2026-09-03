/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import path from "path";
import { SAMPLE_VIDEO_FILENAME, SAMPLE_VIDEO_URL } from "../../constants/videoLibrary";

export { SAMPLE_VIDEO_FILENAME, SAMPLE_VIDEO_URL };

export type ActiveVideoConfig = {
  filename: string;
  source: "sample" | "upload" | "library";
  updated_at: string;
};

export type VideoEntry = {
  filename: string;
  size: number;
  modified_at: string;
  url: string;
  is_sample: boolean;
};

export function projectRoot(): string {
  if (process.env.CDSW_PROJECT_DIR) {
    return process.env.CDSW_PROJECT_DIR;
  }
  return path.join(process.cwd(), "..", "..");
}

export function videosDir(): string {
  if (process.env.VIDEOS_DIR) {
    return process.env.VIDEOS_DIR;
  }
  return path.join(projectRoot(), "videos");
}

export function activeVideoConfigPath(): string {
  return path.join(projectRoot(), "cai", "config", "active_video.json");
}

export function ensureVideosDir(): string {
  const dir = videosDir();
  fs.mkdirSync(dir, { recursive: true });
  fs.mkdirSync(path.dirname(activeVideoConfigPath()), { recursive: true });
  return dir;
}

export function safeVideoFilename(name: string): string {
  const base = path.basename(name);
  if (!/^[a-zA-Z0-9._-]+\.mp4$/i.test(base)) {
    throw new Error("Only .mp4 filenames with safe characters are allowed");
  }
  return base;
}

export function sanitizeUploadFilename(name: string): string {
  let base = path.basename(name).trim().replace(/\s+/g, "_");
  if (!base.toLowerCase().endsWith(".mp4")) {
    base = `${base.replace(/\.[^.]+$/, "")}.mp4`;
  }
  base = base.replace(/[^a-zA-Z0-9._-]/g, "_");
  return safeVideoFilename(base);
}

export function videoFilePath(filename: string): string {
  return path.join(videosDir(), safeVideoFilename(filename));
}

export function readActiveVideo(): ActiveVideoConfig | null {
  const configPath = activeVideoConfigPath();
  if (!fs.existsSync(configPath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(configPath, "utf8")) as ActiveVideoConfig;
  } catch {
    return null;
  }
}

export function writeActiveVideo(filename: string, source: ActiveVideoConfig["source"]): ActiveVideoConfig {
  const payload: ActiveVideoConfig = {
    filename: safeVideoFilename(filename),
    source,
    updated_at: new Date().toISOString(),
  };
  fs.writeFileSync(activeVideoConfigPath(), JSON.stringify(payload, null, 2) + "\n");
  return payload;
}

export function resolveActiveFilename(): string | null {
  const active = readActiveVideo();
  if (active && fs.existsSync(videoFilePath(active.filename))) {
    return active.filename;
  }
  const samplePath = videoFilePath(SAMPLE_VIDEO_FILENAME);
  if (fs.existsSync(samplePath)) {
    writeActiveVideo(SAMPLE_VIDEO_FILENAME, "sample");
    return SAMPLE_VIDEO_FILENAME;
  }
  return null;
}

export function listVideos(): VideoEntry[] {
  ensureVideosDir();
  const dir = videosDir();
  const entries = fs
    .readdirSync(dir)
    .filter((name) => name.toLowerCase().endsWith(".mp4"))
    .map((filename) => {
      const filePath = path.join(dir, filename);
      const stat = fs.statSync(filePath);
      return {
        filename,
        size: stat.size,
        modified_at: stat.mtime.toISOString(),
        url: `/api/videos/${encodeURIComponent(filename)}`,
        is_sample: filename === SAMPLE_VIDEO_FILENAME,
      };
    })
    .sort((a, b) => b.modified_at.localeCompare(a.modified_at));
  return entries;
}

export async function downloadSampleVideo(): Promise<string> {
  ensureVideosDir();
  const dest = videoFilePath(SAMPLE_VIDEO_FILENAME);
  if (fs.existsSync(dest) && fs.statSync(dest).size > 1024) {
    writeActiveVideo(SAMPLE_VIDEO_FILENAME, "sample");
    return SAMPLE_VIDEO_FILENAME;
  }

  const response = await fetch(SAMPLE_VIDEO_URL);
  if (!response.ok) {
    throw new Error(`Failed to download sample video (HTTP ${response.status})`);
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(dest, buffer);
  writeActiveVideo(SAMPLE_VIDEO_FILENAME, "sample");
  return SAMPLE_VIDEO_FILENAME;
}

export function saveUploadedVideo(filename: string, data: Buffer): string {
  ensureVideosDir();
  const safeName = sanitizeUploadFilename(filename);
  const dest = videoFilePath(safeName);
  fs.writeFileSync(dest, data);
  writeActiveVideo(safeName, "upload");
  return safeName;
}
