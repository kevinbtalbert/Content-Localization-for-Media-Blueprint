/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { NextResponse } from "next/server";
import fs from "fs";
import {
  downloadSampleVideo,
  listMedia,
  mediaDir,
  mediaFilePath,
  resolveActiveFilename,
  safeMediaFilename,
  saveUploadedMedia,
  sanitizeUploadFilename,
  SAMPLE_VIDEO_FILENAME,
  SAMPLE_VIDEO_URL,
  writeActiveVideo,
} from "@/app/api/utils/mediaLibrary";

const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024;

export function mediaFileUrl(filename: string, apiPrefix = "/api/media"): string {
  return `${apiPrefix}/${encodeURIComponent(filename)}`;
}

export async function getMediaLibraryJson(apiPrefix = "/api/media") {
  const videos = listMedia();
  const active = resolveActiveFilename();
  const sampleCached = fs.existsSync(mediaFilePath(SAMPLE_VIDEO_FILENAME));
  return {
    videos: videos.map((entry) => ({
      ...entry,
      url: mediaFileUrl(entry.filename, apiPrefix),
    })),
    active,
    media_dir: mediaDir(),
    sample_cached: sampleCached,
    sample_filename: SAMPLE_VIDEO_FILENAME,
    sample_url: SAMPLE_VIDEO_URL,
  };
}

export async function handleMediaGet(apiPrefix = "/api/media") {
  try {
    return NextResponse.json(await getMediaLibraryJson(apiPrefix));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to list media";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function handleMediaPost(request: Request, apiPrefix = "/api/media") {
  try {
    const contentType = request.headers.get("content-type") || "";

    if (contentType.includes("multipart/form-data") || contentType.includes("video/")) {
      const url = new URL(request.url);
      const filenameParam = url.searchParams.get("filename");
      const buffer = Buffer.from(await request.arrayBuffer());
      if (buffer.length > MAX_UPLOAD_BYTES) {
        return NextResponse.json({ error: "File size must not exceed 1GB" }, { status: 400 });
      }
      const sourceName = filenameParam || "upload.mp4";
      const filename = saveUploadedMedia(sanitizeUploadFilename(sourceName), buffer);
      return NextResponse.json({
        filename,
        url: mediaFileUrl(filename, apiPrefix),
        active: filename,
      });
    }

    const body = await request.json();
    const action = body.action as string;

    if (action === "load-sample") {
      const filename = await downloadSampleVideo();
      return NextResponse.json({
        filename,
        url: mediaFileUrl(filename, apiPrefix),
        active: filename,
        cached: true,
      });
    }

    if (action === "select") {
      const filename = safeMediaFilename(String(body.filename || ""));
      if (!fs.existsSync(mediaFilePath(filename))) {
        return NextResponse.json({ error: "Video not found in library" }, { status: 404 });
      }
      writeActiveVideo(filename, "library");
      return NextResponse.json({
        filename,
        url: mediaFileUrl(filename, apiPrefix),
        active: filename,
      });
    }

    return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Media action failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function handleMediaUploadPost(request: Request, apiPrefix = "/api/media") {
  try {
    const url = new URL(request.url);
    const filenameParam = url.searchParams.get("filename");
    if (!filenameParam) {
      return NextResponse.json({ error: "Missing filename query parameter" }, { status: 400 });
    }
    const buffer = Buffer.from(await request.arrayBuffer());
    if (buffer.length > MAX_UPLOAD_BYTES) {
      return NextResponse.json({ error: "File size must not exceed 1GB" }, { status: 400 });
    }
    const filename = saveUploadedMedia(filenameParam, buffer);
    return NextResponse.json({
      filename,
      url: mediaFileUrl(filename, apiPrefix),
      active: filename,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
