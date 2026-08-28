/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import fs from "fs";
import type {
  AudioDiarizationInfo,
  AudioSegmentInfo,
} from "../../../generated_protos/nvidia/ai4m/activespeakerdetection/v1/activespeakerdetection";

const ROWS_PER_CHUNK = 10;
const S2S_SERVICE = process.env.S2S_SERVICE;

/** ElevenLabs diarization: top-level .words[] with text, start/end (seconds), type, speakerId */
interface ElevenLabsWord {
  text?: string;
  start?: number;
  end?: number;
  type?: string;
  speakerId?: string;
}

/** Camb AI diarization: top-level array of {start, end, text, speaker} */
interface CambAiSegment {
  start?: number;
  end?: number;
  text?: string;
  speaker?: string;
}

/**
 * Parse "Speaker N" label to a zero-based integer (same as Python _parse_studio_speaker_id).
 */
function parseCambAiSpeakerId(speaker: string | undefined): number {
  if (!speaker) return 0;
  // "SPEAKER_0" format: underscore-separated, already zero-based
  if (speaker.includes("_")) {
    const suffix = speaker.split("_").pop() ?? "";
    const n = parseInt(suffix, 10);
    return isNaN(n) ? 0 : n;
  }
  // "Speaker 1" format: space-separated, one-based → zero-based
  const match = speaker.match(/(\d+)$/);
  if (!match) return 0;
  return Math.max(0, parseInt(match[1], 10) - 1);
}

/**
 * Convert Camb AI diarization JSON to AudioDiarizationInfo.
 * Camb AI format: [{start, end, text, speaker}] with times in seconds.
 */
export function parseCambAiDiarization(buffer: Buffer): AudioDiarizationInfo | null {
  if (!buffer?.length) return null;
  let data: CambAiSegment[];
  try {
    const parsed = JSON.parse(buffer.toString("utf-8"));
    // Unwrap {"transcript": [...]} wrapper (matches Python _build_segments_from_camb_json)
    if (parsed && !Array.isArray(parsed) && Array.isArray(parsed.transcript)) {
      data = parsed.transcript;
    } else {
      data = parsed;
    }
  } catch {
    return null;
  }
  if (!Array.isArray(data) || !data.length) return null;

  const segments: AudioSegmentInfo[] = [];
  for (const seg of data) {
    segments.push({
      start_time: Math.round((seg.start ?? 0) * 1000),
      end_time: Math.round((seg.end ?? 0) * 1000),
      speaker_id: parseCambAiSpeakerId(seg.speaker),
      word: seg.text || undefined,
    });
  }

  return segments.length ? { segments, transcript: undefined } : null;
}

/**
 * Convert ElevenLabs diarization JSON to AudioDiarizationInfo (segments with start_time/end_time in ms, speaker_id, word).
 * Merges consecutive words with the same speaker into segments.
 */
export function parseElevenLabsDiarization(buffer: Buffer): AudioDiarizationInfo | null {
  if (!buffer?.length) return null;
  let data: { words?: ElevenLabsWord[] };
  try {
    data = JSON.parse(buffer.toString("utf-8"));
  } catch {
    return null;
  }
  const words = Array.isArray(data?.words) ? data.words : [];
  if (!words.length) return null;

  const segments: AudioSegmentInfo[] = [];
  let curSpeaker = "";
  let curWords: string[] = [];
  let curStart: number | null = null;
  let curEnd: number | null = null;

  const flush = () => {
    if (!curWords.length || curStart == null || curEnd == null) return;
    const id = curSpeaker.replace("speaker_", "speaker").match(/(\d+)$/)?.[1];
    segments.push({
      start_time: Math.round(curStart * 1000),
      end_time: Math.round(curEnd * 1000),
      speaker_id: id != null ? parseInt(id, 10) : 0,
      word: curWords.join(" ").trim() || undefined,
    });
  };

  for (const w of words) {
    if (w.type !== "word" || !w.text) continue;
    const sid = w.speakerId?.replace("speaker_", "speaker") ?? "speaker0";
    if (curSpeaker && sid !== curSpeaker) {
      flush();
      curWords = [];
      curStart = null;
      curEnd = null;
    }
    curSpeaker = sid;
    if (curStart == null) curStart = w.start ?? 0;
    curEnd = w.end ?? curEnd ?? curStart;
    curWords.push(w.text);
  }
  flush();

  return segments.length ? { segments, transcript: undefined } : null;
}

/**
 * Parse diarization from a Buffer, routing by S2S_SERVICE.
 * CAMB_DUBBING → Camb AI parser, else → ElevenLabs parser.
 */
export function parseDiarization(buffer: Buffer): AudioDiarizationInfo | null {
  if (S2S_SERVICE === "CAMB_DUBBING") {
    return parseCambAiDiarization(buffer);
  }
  return parseElevenLabsDiarization(buffer);
}

/**
 * Parse diarization from a file, routing by S2S_SERVICE.
 */
export function parseDiarizationFromFile(filePath: string): AudioDiarizationInfo | null {
  if (!filePath || !fs.existsSync(filePath)) return null;
  return parseDiarization(fs.readFileSync(filePath));
}

/** Chunk for controller (same as client/controller/app.py chunk_diarization_info). */
export function chunkDiarization(
  diarization: AudioDiarizationInfo,
  rowsPerChunk: number = ROWS_PER_CHUNK,
): AudioDiarizationInfo[] {
  const segs = diarization.segments ?? [];
  if (!segs.length) return [];
  const out: AudioDiarizationInfo[] = [];
  for (let i = 0; i < segs.length; i += rowsPerChunk) {
    out.push({ segments: segs.slice(i, i + rowsPerChunk), transcript: undefined });
  }
  return out;
}
