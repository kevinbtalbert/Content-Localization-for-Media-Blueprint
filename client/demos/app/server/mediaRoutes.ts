/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { IncomingMessage, ServerResponse } from "http";
import fs from "fs";
import { URL } from "url";
import {
  downloadSampleVideo,
  listMedia,
  mediaDir,
  mediaFilePath,
  resolveActiveFilename,
  safeMediaFilename,
  SAMPLE_VIDEO_FILENAME,
  SAMPLE_VIDEO_URL,
  saveUploadedMedia,
  writeActiveVideo,
} from "../api/utils/mediaLibrary";
import logger from "../utils/logger";

const MAX_UPLOAD_BYTES = 1024 * 1024 * 1024;

function sendJson(res: ServerResponse, status: number, payload: unknown): void {
  const body = JSON.stringify(payload);
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.setHeader("Content-Length", Buffer.byteLength(body));
  res.end(body);
}

async function readBody(req: IncomingMessage, limit = 1024 * 1024): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buf.length;
    if (total > limit) {
      throw new Error("Request body too large");
    }
    chunks.push(buf);
  }
  return Buffer.concat(chunks);
}

async function readUploadBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buf.length;
    if (total > MAX_UPLOAD_BYTES) {
      throw new Error("File size must not exceed 1GB");
    }
    chunks.push(buf);
  }
  return Buffer.concat(chunks);
}

function serveMediaFile(req: IncomingMessage, res: ServerResponse, filename: string): void {
  const filePath = mediaFilePath(filename);
  if (!fs.existsSync(filePath)) {
    sendJson(res, 404, { error: "File not found" });
    return;
  }

  const stat = fs.statSync(filePath);
  const fileSize = stat.size;
  const range = req.headers.range;
  const headers: Record<string, string> = {
    "Content-Type": "video/mp4",
    "Accept-Ranges": "bytes",
  };

  let start = 0;
  let end = fileSize - 1;
  if (range) {
    const parts = range.replace(/bytes=/, "").split("-");
    start = parseInt(parts[0], 10);
    end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
    headers["Content-Range"] = `bytes ${start}-${end}/${fileSize}`;
    headers["Content-Length"] = String(end - start + 1);
    res.statusCode = 206;
  } else {
    headers["Content-Length"] = String(fileSize);
    res.statusCode = 200;
  }

  Object.entries(headers).forEach(([key, value]) => res.setHeader(key, value));
  fs.createReadStream(filePath, { start, end }).pipe(res);
}

async function handleMediaList(_req: IncomingMessage, res: ServerResponse): Promise<void> {
  const videos = listMedia();
  const active = resolveActiveFilename();
  const sampleCached = fs.existsSync(mediaFilePath(SAMPLE_VIDEO_FILENAME));
  sendJson(res, 200, {
    videos,
    active,
    media_dir: mediaDir(),
    sample_cached: sampleCached,
    sample_filename: SAMPLE_VIDEO_FILENAME,
    sample_url: SAMPLE_VIDEO_URL,
  });
}

async function handleMediaPost(req: IncomingMessage, res: ServerResponse, url: URL): Promise<void> {
  const contentType = req.headers["content-type"] || "";

  if (contentType.includes("application/json")) {
    const body = JSON.parse((await readBody(req)).toString("utf8")) as {
      action?: string;
      filename?: string;
    };
    if (body.action === "load-sample") {
      const filename = await downloadSampleVideo();
      sendJson(res, 200, {
        filename,
        url: `/api/media/${encodeURIComponent(filename)}`,
        active: filename,
        cached: true,
      });
      return;
    }
    if (body.action === "select") {
      const filename = safeMediaFilename(String(body.filename || ""));
      if (!fs.existsSync(mediaFilePath(filename))) {
        sendJson(res, 404, { error: "Video not found in library" });
        return;
      }
      writeActiveVideo(filename, "library");
      sendJson(res, 200, {
        filename,
        url: `/api/media/${encodeURIComponent(filename)}`,
        active: filename,
      });
      return;
    }
    sendJson(res, 400, { error: `Unknown action: ${body.action}` });
    return;
  }

  sendJson(res, 415, { error: "Use POST /api/media/upload for file uploads" });
}

async function handleMediaUpload(req: IncomingMessage, res: ServerResponse, url: URL): Promise<void> {
  const filenameParam = url.searchParams.get("filename");
  if (!filenameParam) {
    sendJson(res, 400, { error: "Missing filename query parameter" });
    return;
  }

  try {
    const data = await readUploadBody(req);
    const filename = saveUploadedMedia(filenameParam, data);
    sendJson(res, 200, {
      filename,
      url: `/api/media/${encodeURIComponent(filename)}`,
      active: filename,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed";
    sendJson(res, 400, { error: message });
  }
}

export async function handleMediaApi(req: IncomingMessage, res: ServerResponse): Promise<boolean> {
  if (!req.url) {
    return false;
  }

  const url = new URL(req.url, "http://127.0.0.1");
  const pathname = url.pathname.replace(/^\/api\/videos(?=\/|$)/, "/api/media");
  url.pathname = pathname;

  if (!pathname.startsWith("/api/media")) {
    return false;
  }

  try {
    if (url.pathname === "/api/media" && req.method === "GET") {
      await handleMediaList(req, res);
      return true;
    }

    if (url.pathname === "/api/media" && req.method === "POST") {
      await handleMediaPost(req, res, url);
      return true;
    }

    if (url.pathname === "/api/media/upload" && req.method === "POST") {
      await handleMediaUpload(req, res, url);
      return true;
    }

    const fileMatch = url.pathname.match(/^\/api\/media\/([^/]+)$/);
    if (fileMatch && req.method === "GET") {
      serveMediaFile(req, res, decodeURIComponent(fileMatch[1]));
      return true;
    }

    sendJson(res, 404, { error: "Media API route not found" });
    return true;
  } catch (error) {
    logger.error("[media] API error:", error);
    sendJson(res, 500, { error: error instanceof Error ? error.message : "Media API failed" });
    return true;
  }
}
