/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import path from "path";
import { spawn } from "child_process";
import { ElevenLabsClient, ElevenLabsEnvironment } from "@elevenlabs/elevenlabs-js";
import logger from "../../utils/logger";
import { envOrPersisted } from "./persistedConfig";

function elevenLabsApiKey(): string {
  return envOrPersisted("ELEVENLABS_API_KEY", "elevenlabs_api_key") || "";
}

let elevenLabsClient: ElevenLabsClient | null = null;

/**
 * Get or initialize the ElevenLabs client
 */
export function getElevenLabsClient(): ElevenLabsClient | null {
  const apiKey = elevenLabsApiKey();
  if (!elevenLabsClient && apiKey) {
    elevenLabsClient = new ElevenLabsClient({
      apiKey,
      environment: ElevenLabsEnvironment.Production,
    });
  }
  return elevenLabsClient;
}

/**
 * Isolate voice from background noise using ElevenLabs audio isolation API
 * API returns MP3; we convert to WAV so the output file matches the .wav extension.
 * @param audioFilePath - Path to the input audio file
 * @param outputPath - Path where the isolated audio will be saved (must end in .wav)
 * @returns Promise resolving to the output file path
 */
export async function isolateAudio(audioFilePath: string, outputPath: string): Promise<string> {
  const client = getElevenLabsClient();
  if (!client) {
    throw new Error("ElevenLabs API key not set. Cannot perform voice isolation.");
  }

  if (!fs.existsSync(audioFilePath)) {
    throw new Error(`Audio file not found: ${audioFilePath}`);
  }

  logger.info(`Starting voice isolation for: ${audioFilePath}`);

  try {
    // Ensure output directory exists
    const outputDir = path.dirname(outputPath);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // ElevenLabs returns MP3 (with ID3); write to temp file then convert to WAV
    const tempPath = `${outputPath}.tmp`;

    // Call ElevenLabs audio isolation API (returns a promise with a ReadableStream)
    const audioStream = await client.audioIsolation.convert({
      audio: fs.createReadStream(audioFilePath),
    });

    // Write the isolated audio stream to the temp file (MP3)
    const writeStream = fs.createWriteStream(tempPath);

    // Convert ReadableStream to async iterable and write chunks
    const reader = (audioStream as ReadableStream<Uint8Array>).getReader();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        writeStream.write(Buffer.from(value));
      }
    } finally {
      reader.releaseLock();
    }
    writeStream.end();

    await new Promise<void>((resolve, reject) => {
      writeStream.on("finish", resolve);
      writeStream.on("error", reject);
    });

    // Convert MP3 → WAV so the .wav file is actually WAV (controller expects PCM)
    await new Promise<void>((resolve, reject) => {
      const ffmpeg = spawn("ffmpeg", ["-y", "-i", tempPath, outputPath], {
        stdio: ["ignore", "pipe", "pipe"],
      });
      let stderr = "";
      ffmpeg.stderr?.on("data", (data: Buffer) => {
        stderr += data.toString();
      });
      ffmpeg.on("close", (code) => {
        try {
          fs.unlinkSync(tempPath);
        } catch {
          // ignore
        }
        if (code === 0) {
          logger.info(`Voice isolation completed. Output saved to: ${outputPath} (converted to WAV)`);
          resolve();
        } else {
          reject(new Error(`ffmpeg failed (${code}): ${stderr.slice(-500)}`));
        }
      });
      ffmpeg.on("error", (err) => {
        try {
          fs.unlinkSync(tempPath);
        } catch {
          // ignore
        }
        reject(err);
      });
    });

    return outputPath;
  } catch (error) {
    logger.error(`Error during voice isolation: ${error}`);
    throw error;
  }
}

/**
 * Perform diarization using ElevenLabs speech-to-text API
 * @param audioFilePath - Path to the input audio file
 * @param streamId - Unique stream identifier
 * @returns Promise resolving to the diarization response
 */
export async function performDiarization(audioFilePath: string, streamId: string): Promise<any> {
  const client = getElevenLabsClient();
  if (!client) {
    logger.warn("ElevenLabs API key not set. Skipping diarization.");
    return null;
  }

  if (!fs.existsSync(audioFilePath)) {
    throw new Error(`Audio file not found for diarization: ${audioFilePath}`);
  }

  logger.info(`Starting ElevenLabs diarization for: ${audioFilePath}`);

  try {
    const response = await client.speechToText.convert({
      modelId: "scribe_v2",
      file: fs.createReadStream(audioFilePath),
      diarize: true,
      enableLogging: false,
    });

    logger.info(`Diarization completed for stream: ${streamId}`);
    return response;
  } catch (error) {
    logger.error(`Error during ElevenLabs diarization: ${error}`);
    throw error;
  }
}

/**
 * Save diarization data to JSON file
 * @param streamId - Unique stream identifier
 * @param diarizationData - The diarization response data
 * @param outputDir - Directory where the file should be saved
 * @returns Promise resolving to the saved file path
 */
export async function saveDiarizationFile(streamId: string, diarizationData: any, outputDir: string): Promise<string> {
  const diarizationFilePath = path.join(outputDir, `${streamId}.json`);
  await fs.promises.writeFile(diarizationFilePath, JSON.stringify(diarizationData, null, 2), "utf-8");
  logger.info(`Diarization saved to ${diarizationFilePath}`);
  return diarizationFilePath;
}
