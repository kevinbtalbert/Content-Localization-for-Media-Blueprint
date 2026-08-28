/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import logger from "@/app/utils/logger";

/**
 * Content type mapping for common media file extensions
 */
const CONTENT_TYPE_MAP: Record<string, string> = {
  ".mp4": "video/mp4",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
};

/**
 * Serves a file with support for range requests (for video/audio streaming)
 *
 * @param filename - The name of the file to serve
 * @param baseDir - The base directory where the file is located
 * @param request - The Next.js request object
 * @returns NextResponse with the file stream or error
 */
export async function nextFileServe(filePath: string, request: NextRequest): Promise<NextResponse> {
  try {
    // Check if file exists
    if (!fs.existsSync(filePath)) {
      logger.error("File not found at path:", filePath);
      return NextResponse.json({ error: "File not found" }, { status: 404 });
    }

    // Get file stats
    const stat = fs.statSync(filePath);
    const fileSize = stat.size;
    const range = request.headers.get("range");

    // Determine content type based on file extension
    const ext = path.extname(filePath).toLowerCase();
    const contentType = CONTENT_TYPE_MAP[ext] || "application/octet-stream";

    const headers: Record<string, string> = {
      "Content-Length": fileSize.toString(),
      "Content-Type": contentType,
    };

    let start = 0;
    let end = fileSize - 1;

    // Handle range requests (for streaming)
    if (range) {
      const parts = range.replace(/bytes=/, "").split("-");
      start = parseInt(parts[0], 10);
      end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      headers["Content-Length"] = (end - start + 1).toString();
      headers["Content-Range"] = `bytes ${start}-${end}/${fileSize}`;
      headers["Accept-Ranges"] = "bytes";
    }

    // Create file stream
    const fileStream = fs.createReadStream(filePath, { start, end });

    // Convert to ReadableStream for Next.js response
    const readableStream = new ReadableStream({
      start(controller) {
        let isClosed = false;

        fileStream.on("data", (chunk) => {
          if (!isClosed) {
            try {
              controller.enqueue(chunk);
            } catch (err) {
              // Controller might be closed if stream was cancelled
              logger.debug("Failed to enqueue chunk (stream likely cancelled):", err);
              isClosed = true;
              fileStream.destroy();
            }
          }
        });

        fileStream.on("end", () => {
          if (!isClosed) {
            try {
              controller.close();
              isClosed = true;
            } catch (err) {
              // Controller might already be closed
              logger.debug("Failed to close controller (already closed):", err);
            }
          }
        });

        fileStream.on("error", (err) => {
          if (!isClosed) {
            try {
              controller.error(err);
              isClosed = true;
            } catch (error) {
              // Controller might already be closed
              logger.error("Failed to signal error to controller:", error);
            }
          }
          fileStream.destroy();
        });
      },
      cancel() {
        // Clean up the file stream when the readable stream is cancelled
        logger.debug("Stream cancelled, destroying file stream");
        fileStream.destroy();
      },
    });

    return new NextResponse(readableStream, {
      status: range ? 206 : 200,
      headers,
    });
  } catch (error) {
    logger.error("Error serving file:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
