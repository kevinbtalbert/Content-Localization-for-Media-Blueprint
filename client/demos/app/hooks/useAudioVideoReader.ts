/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { useCallback, useRef } from "react";
import logger from "@/app/utils/logger";

type AudioVideoReaderOptions = {
  sampleRate?: number;
  chunkDuration?: number;
};

// Helper function to create a WAV header for PCM 16-bit mono audio
function createWavHeader(audioBufferLength: number, sampleRate: number) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = (sampleRate * numChannels * bitsPerSample) / 8;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const dataSize = audioBufferLength;
  const buffer = new ArrayBuffer(44);
  const view = new DataView(buffer);

  // "RIFF" chunk descriptor
  view.setUint32(0, 0x52494646, false); // "RIFF"
  view.setUint32(4, 36 + dataSize, true); // file length - 8
  view.setUint32(8, 0x57415645, false); // "WAVE"

  // "fmt " sub-chunk
  view.setUint32(12, 0x666d7420, false); // "fmt "
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (1 for PCM)
  view.setUint16(22, numChannels, true); // NumChannels
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, byteRate, true); // ByteRate
  view.setUint16(32, blockAlign, true); // BlockAlign
  view.setUint16(34, bitsPerSample, true); // BitsPerSample

  // "data" sub-chunk
  view.setUint32(36, 0x64617461, false); // "data"
  view.setUint32(40, dataSize, true); // Subchunk2Size

  return buffer;
}

// Helper function to read video chunks sequentially like video.py does
const readVideoChunksSequentially = async (file: File, chunkSize: number): Promise<ArrayBuffer[]> => {
  const chunks: ArrayBuffer[] = [];
  const reader = new FileReader();

  for (let offset = 0; offset < file.size; offset += chunkSize) {
    const chunk = file.slice(offset, Math.min(offset + chunkSize, file.size));

    const arrayBuffer = await new Promise<ArrayBuffer>((resolve, reject) => {
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = reject;
      reader.readAsArrayBuffer(chunk);
    });

    chunks.push(arrayBuffer);
  }

  return chunks;
};

const useAudioVideoReader = (options: AudioVideoReaderOptions = {}) => {
  const audioContext = useRef<AudioContext | null>(null);

  const startAudioVideoReader = useCallback(
    async (
      file: File,
      onData: (audio: ArrayBuffer, video?: ArrayBuffer) => void,
      onEnd: (totalPackets: number) => void,
      onError: (error: string) => void,
      onProgress?: (sentChunks: number, totalChunks: number) => void,
    ) => {
      const { sampleRate = 16000, chunkDuration = 1 } = options;
      if (audioContext.current && audioContext.current.state === "running") {
        audioContext.current.close();
      }
      const audioCtx = new AudioContext({ sampleRate });
      audioContext.current = audioCtx;
      const arrayBuffer = await file.arrayBuffer();

      let decodedAudio: AudioBuffer | null = null;
      try {
        decodedAudio = await audioCtx.decodeAudioData(arrayBuffer);
      } catch (error) {
        onError(`Failed to decode audio from the video file (${error})`);
        return;
      }

      const audioSampleRate = decodedAudio.sampleRate;
      const chunkSampleSize = chunkDuration * audioSampleRate;
      const totalAudioSamples = decodedAudio.length;

      // Add WAV header to the entire decodedAudio buffer
      const totalSamples = decodedAudio.length;
      const wavDataBuffer = new ArrayBuffer(totalSamples * 2);
      const wavDataView = new DataView(wavDataBuffer);
      const channelData = decodedAudio.getChannelData(0);
      // Convert decodedAudio (Float32Array) to PCM 16-bit
      for (let i = 0; i < totalSamples; i++) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        wavDataView.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }
      const wavHeader = createWavHeader(wavDataBuffer.byteLength, decodedAudio.sampleRate);

      // Concatenate header and PCM data into one ArrayBuffer
      const wavWithHeader = new Uint8Array(wavHeader.byteLength + wavDataBuffer.byteLength);
      wavWithHeader.set(new Uint8Array(wavHeader), 0);
      wavWithHeader.set(new Uint8Array(wavDataBuffer), wavHeader.byteLength);

      // Use the SAME chunk size as the working video.py (64KB)
      const videoChunkSize = 2 * 1024 * 1024; // 2MB - exactly like video.py

      // Prepare all audio chunks first
      const audioChunksList = [];
      for (let i = 0; i < decodedAudio.duration; i += chunkDuration) {
        const startSample = Math.floor(i * audioSampleRate);
        const endSample = Math.min(startSample + chunkSampleSize, totalAudioSamples);
        const audioChunk = decodedAudio.getChannelData(0).slice(startSample, endSample);

        let audioBuffer = new ArrayBuffer(audioChunk.length * 2);
        const pcmView = new DataView(audioBuffer);
        for (let j = 0; j < audioChunk.length; j++) {
          const s = Math.max(-1, Math.min(1, audioChunk[j]));
          pcmView.setInt16(j * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
        }

        if (i === 0) {
          // Add WAV header to first audio chunk
          audioBuffer = new Uint8Array([...new Uint8Array(wavHeader), ...new Uint8Array(audioBuffer)]).buffer;
        }

        audioChunksList.push(audioBuffer);
      }
      const videoChunksList = await readVideoChunksSequentially(file, videoChunkSize);
      logger.info(`Generated ${videoChunksList.length} video chunks`);

      const totalChunks = Math.max(audioChunksList.length, videoChunksList.length);
      onProgress?.(0, totalChunks);

      // Send synchronized audio-video chunks
      const minChunks = Math.min(audioChunksList.length, videoChunksList.length);
      for (let i = 0; i < minChunks; i++) {
        onData(audioChunksList[i], videoChunksList[i]);
        onProgress?.(i + 1, totalChunks);
      }

      // Send remaining video chunks (if any)
      for (let i = minChunks; i < videoChunksList.length; i++) {
        onData(new ArrayBuffer(0), videoChunksList[i]);
        onProgress?.(i + 1, totalChunks);
      }

      // Send remaining audio chunks (if any)
      for (let i = minChunks; i < audioChunksList.length; i++) {
        onData(audioChunksList[i]);
        onProgress?.(i + 1, totalChunks);
      }

      onEnd(totalChunks);
    },
    [options],
  );

  const stopAudioVideoReader = useCallback(() => {
    if (audioContext.current) {
      audioContext.current.close();
    }
  }, []);

  return { startAudioVideoReader, stopAudioVideoReader };
};

export default useAudioVideoReader;
