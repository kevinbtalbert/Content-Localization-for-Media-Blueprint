/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { WebSocket } from "ws";
import logger from "../../utils/logger";
import type { CodecId } from "../../utils/codecConfig";
import { ensureOutputDirs } from "./content-localization/config";
import { ContentLocalizationHandler } from "./content-localization/ContentLocalizationHandler";

// Ensure output directories exist when the module loads
ensureOutputDirs();

/**
 * Content localization WebSocket orchestrator.
 * Message types:
 * - localization_configs: source/target language, codecs, voice isolation, optional diarization file
 * - data_chunk: { audio, video } base64 chunks
 * - data_end: no more chunks; triggers preprocessing (if enabled) then localization stream end
 *
 * On JSON parse or data_chunk base64 decode errors, sends { type: "error", data: { error } } to client.
 */
export default function contentLocalization(ws: WebSocket, _urlPath: string): void {
  const handler = new ContentLocalizationHandler(ws);

  ws.on("close", () => {
    logger.info("[ContentLocalization] WebSocket closed, stopping processing");
    handler.cancel();
  });

  ws.on("message", async (message: MessageEvent) => {
    let data: { type: string; data?: Record<string, unknown> };
    try {
      data = JSON.parse((message as unknown as Buffer).toString());
    } catch (parseError) {
      const errorMessage = parseError instanceof Error ? parseError.message : "Invalid JSON in message";
      logger.error("[ContentLocalization] Failed to parse message", { error: errorMessage });
      ws.send(JSON.stringify({ type: "error", data: { error: `Parse error: ${errorMessage}` } }));
      return;
    }

    if (data.type === "localization_configs") {
      const config = data.data;
      let customDiarizationFile: Buffer | null = null;
      if (config?.diarization_file) {
        try {
          customDiarizationFile = Buffer.from(config.diarization_file as string, "base64");
          logger.info("[ContentLocalization] Received custom diarization file");
        } catch (error) {
          logger.error("[ContentLocalization] Failed to decode diarization file", { error });
        }
      }
      if (config) {
        handler.setData({
          sourceLanguage: config.source_language as string,
          targetLanguage: config.target_language as string,
          streamingCodecId: (config.streaming_codec_id as CodecId) ?? "default",
          downloadCodecId: (config.download_codec_id as CodecId) ?? "default",
          voiceIsolation: config.voice_isolation !== undefined ? Boolean(config.voice_isolation) : true,
          customDiarizationFile,
        });
      }
    } else if (data.type === "data_chunk") {
      try {
        const chunkPayload = data.data as { audio?: string; video?: string } | undefined;
        const audio = Buffer.from(chunkPayload?.audio ?? "", "base64");
        const video = Buffer.from(chunkPayload?.video ?? "", "base64");
        handler.pushData(audio, video);
      } catch (chunkError) {
        const errorMessage = chunkError instanceof Error ? chunkError.message : "Invalid data_chunk payload";
        logger.error("[ContentLocalization] Failed to process data_chunk", {
          error: errorMessage,
        });
        ws.send(
          JSON.stringify({
            type: "error",
            data: { error: `Data chunk error: ${errorMessage}` },
          }),
        );
      }
    } else if (data.type === "data_end") {
      await handler.streamEnd();
    }
  });
}
