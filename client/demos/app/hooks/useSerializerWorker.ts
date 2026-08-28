/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { useRef, useEffect, useCallback } from "react";
import logger from "@/app/utils/logger";

interface SerializerResult {
  success: boolean;
  index: number;
  message?: string; // Stringified JSON message ready to send
  error?: string;
}

/**
 * Hook to manage a Web Worker for base64 encoding and JSON serialization
 * Offloads CPU-intensive serialization and stringify to a separate thread.
 * Pass stable callbacks (e.g. useCallback with stable deps) so the worker is not recreated on re-renders.
 */
export const useSerializerWorker = (
  onSerialized: (message: string, index: number) => void,
  onError: (error: string) => void,
) => {
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    workerRef.current = new Worker(new URL("../workers/serializer.worker.ts", import.meta.url));

    workerRef.current.onmessage = (e: MessageEvent<SerializerResult>) => {
      const result = e.data;

      if (result.success && result.message) {
        onSerialized(result.message, result.index);
      } else if (result.error) {
        logger.error("Worker serialization error:", result.error);
        onError(`Serialization failed: ${result.error}. Please try again.`);
      }
    };

    workerRef.current.onerror = (error) => {
      logger.error("Worker error:", error);
      onError("Serialization worker failed. Please refresh the page and try again.");
    };

    return () => {
      workerRef.current?.terminate();
      workerRef.current = null;
    };
  }, [onSerialized, onError]);

  const serializeChunk = useCallback((audio: ArrayBuffer, video: ArrayBuffer | undefined, index: number) => {
    if (!workerRef.current) {
      logger.error("Worker not initialized");
      return;
    }

    workerRef.current.postMessage({ audio, video, index });
  }, []);

  return { serializeChunk };
};
