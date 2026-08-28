/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import type { WebSocket } from "ws";
import { nanoid } from "nanoid";
import logger from "../../../utils/logger";
import type { CodecId } from "../../../utils/codecConfig";
import { AUDIO_OUTPUT_DIR, DIARIZATION_OUTPUT_DIR } from "./config";
import { PIPELINE_STATUS } from "./pipelineStatus";
import { preprocessAudioEndToEnd, readProcessedAudioAsChunks } from "./preprocessAudio";
import { createLocalizationStream } from "./localizationStream";
import { parseDiarization, parseDiarizationFromFile, chunkDiarization } from "./diarization";
import { getEnablePreprocessingFromEnv } from "../../utils/audioProcessing";

export interface HandlerConfig {
  sourceLanguage: string;
  targetLanguage: string;
  streamingCodecId: CodecId;
  downloadCodecId: CodecId;
  voiceIsolation: boolean;
  customDiarizationFile: Buffer | null;
}

/**
 * Handles one content-localization WebSocket session:
 * - Receives config (localization_configs) and data chunks (data_chunk / data_end)
 * - If preprocessing is enabled: buffers chunks, runs preprocessing on end, then
 *   streams processed audio + original video to the controller (on preprocessing
 *   failure, streams original buffered audio/video instead).
 * - If not: streams chunks directly to the controller
 */
export class ContentLocalizationHandler {
  private ws: WebSocket;
  private onData: ((audio: Buffer, video: Buffer) => void) | null = null;
  private onEnd: (() => void) | null = null;
  private cancelProcessing: (() => void) | null = null;
  private streamId: string | undefined;
  private sourceLanguage: string | undefined;
  private targetLanguage: string | undefined;
  private streamingCodecId: CodecId = "default";
  private downloadCodecId: CodecId = "default";
  private voiceIsolation = true;
  private customDiarizationFile: Buffer | null = null;
  /** After preprocessing, path to diarization file (from custom upload or ElevenLabs). */
  private processedDiarizationFilePath: string | undefined | null = undefined;
  /** When false, preprocessing is not available. */
  private enablePreprocessing = true;
  /** When true, we buffer chunks and run preprocessing before sending to controller */
  private shouldPreProcessAudio = true;
  private audioBuffer: Buffer[] = [];
  private videoBuffer: Buffer[] = [];
  private sentUploadingStatus = false;

  constructor(ws: WebSocket) {
    this.ws = ws;
  }

  /** Notify client of pipeline status for UI (uploading | preprocessing | localizing) */
  private sendStatus(status: PIPELINE_STATUS): void {
    try {
      this.ws.send(JSON.stringify({ type: "status", data: { status } }));
    } catch (err) {
      logger.debug("[ContentLocalization] Failed to send status", { status, err });
    }
  }

  /** Send a non-fatal warning to the client UI */
  private sendWarning(message: string): void {
    try {
      this.ws.send(JSON.stringify({ type: "warning", data: { message } }));
    } catch (err) {
      logger.debug("[ContentLocalization] Failed to send warning", { message, err });
    }
  }

  /** Update config from client (languages, codecs, voice isolation, diarization file) */
  public setData(data: HandlerConfig): void {
    this.sourceLanguage = data.sourceLanguage;
    this.targetLanguage = data.targetLanguage;
    this.streamingCodecId = data.streamingCodecId;
    this.downloadCodecId = data.downloadCodecId;
    this.voiceIsolation = data.voiceIsolation;
    this.customDiarizationFile = data.customDiarizationFile;
    this.enablePreprocessing = getEnablePreprocessingFromEnv();
    this.shouldPreProcessAudio =
      this.enablePreprocessing && (this.voiceIsolation || this.customDiarizationFile === null);
    logger.info("[ContentLocalization] Config updated", {
      source: this.sourceLanguage,
      target: this.targetLanguage,
      voiceIsolation: this.voiceIsolation,
      preprocess: this.shouldPreProcessAudio,
    });
  }

  /** Push one audio/video chunk: either buffer it (preprocess) or send to controller. Caller passes Buffer (decode once at WS entry). */
  public pushData(audio: Buffer, video: Buffer): void {
    if (!this.sentUploadingStatus) {
      this.sentUploadingStatus = true;
      this.sendStatus(PIPELINE_STATUS.UPLOADING);
    }
    if (this.shouldPreProcessAudio) {
      this.audioBuffer.push(audio);
      this.videoBuffer.push(video);
    } else {
      this.streamToUpstream(audio, video);
    }
  }

  /**
   * Send chunk to controller. Caller must pass Buffer (we control the flow: decode at call site).
   */
  public streamToUpstream(audio: Buffer, video: Buffer): void {
    if (!this.onData) {
      // Diarization from custom upload or from preprocessing (same parser for all formats).
      const diarizationChunks = (() => {
        if (this.customDiarizationFile && this.customDiarizationFile.length > 0) {
          const info = parseDiarization(this.customDiarizationFile);
          return info ? chunkDiarization(info) : [];
        }
        if (this.processedDiarizationFilePath) {
          const info = parseDiarizationFromFile(this.processedDiarizationFilePath);
          return info ? chunkDiarization(info) : [];
        }
        return [];
      })();
      // Bypass ASD when no diarization is available (mirrors Python client auto-detect)
      const bypassAsd = diarizationChunks.length === 0;
      if (bypassAsd) {
        logger.info("[ContentLocalization] No diarization available, bypassing ASD");
      }
      const stream = createLocalizationStream((payload) => this.ws.send(payload), {
        sourceLanguage: this.sourceLanguage,
        targetLanguage: this.targetLanguage,
        streamingCodecId: this.streamingCodecId,
        downloadCodecId: this.downloadCodecId,
        diarizationChunks,
        bypassAsd,
      });
      this.onData = stream.onData;
      this.onEnd = stream.onEnd;
      this.cancelProcessing = stream.cancelProcessing;
      this.streamId = stream.streamId;
    }
    this.onData(audio, video);
  }

  /**
   * Stream two arrays of chunks to the controller (paired by index, then remainder as audio-only or video-only), then end.
   */
  private streamBuffersAndEnd(audioChunks: Buffer[], videoChunks: Buffer[]): void {
    let index = 0;
    while (index < audioChunks.length && index < videoChunks.length) {
      this.streamToUpstream(audioChunks[index], videoChunks[index]);
      index++;
    }
    while (index < audioChunks.length) {
      this.streamToUpstream(audioChunks[index], Buffer.alloc(0));
      index++;
    }
    while (index < videoChunks.length) {
      this.streamToUpstream(Buffer.alloc(0), videoChunks[index]);
      index++;
    }
    this.onEnd?.();
  }

  /**
   * Called when client sends data_end.
   * If preprocessing: run preprocessing, then stream processed audio + video and end.
   * If preprocessing fails, streams original buffered audio/video and ends (non-blocking fallback).
   * Otherwise: just end the stream.
   */
  public async streamEnd(): Promise<void> {
    if (this.shouldPreProcessAudio) {
      try {
        this.sendStatus(PIPELINE_STATUS.PREPROCESSING);
        const streamId = this.streamId ?? nanoid(36);
        logger.info("[ContentLocalization] Preprocessing buffered audio", {
          streamId,
          chunks: this.audioBuffer.length,
        });

        const processedAudio = await preprocessAudioEndToEnd({
          streamId,
          audioChunks: this.audioBuffer,
          voiceIsolation: this.voiceIsolation,
          customDiarizationFile: this.customDiarizationFile ?? null,
          audioOutputDir: AUDIO_OUTPUT_DIR,
          diarizationOutputDir: DIARIZATION_OUTPUT_DIR,
          sourceLanguage: this.sourceLanguage,
        });
        this.processedDiarizationFilePath = processedAudio.diarizationFilePath;

        // Send non-fatal warning to the UI (e.g. diarization or voice isolation failed)
        if (processedAudio.warning) {
          this.sendWarning(processedAudio.warning);
        }

        let processedChunks: Buffer[] = this.audioBuffer;

        if (processedAudio.audioFilePath) {
          processedChunks = readProcessedAudioAsChunks(processedAudio.audioFilePath, this.audioBuffer.length);
        }

        logger.info("[ContentLocalization] Streaming processed audio to controller", {
          chunks: processedChunks.length,
          videoChunks: this.videoBuffer.length,
        });

        this.sendStatus(PIPELINE_STATUS.LOCALIZING);
        this.streamBuffersAndEnd(processedChunks, this.videoBuffer);
      } catch (error) {
        logger.error("[ContentLocalization] Preprocessing failed, streaming original audio", {
          error,
        });
        this.sendWarning("Preprocessing failed. Processing will continue with original audio.");
        this.sendStatus(PIPELINE_STATUS.LOCALIZING);
        this.streamBuffersAndEnd(this.audioBuffer, this.videoBuffer);
      }
    } else {
      this.sendStatus(PIPELINE_STATUS.LOCALIZING);
      this.onEnd?.();
    }
  }

  /** Cancel the current localization stream (e.g. on WebSocket close) */
  public cancel(): void {
    this.cancelProcessing?.();
  }
}
