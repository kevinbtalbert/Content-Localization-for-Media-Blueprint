/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { useCallback, useEffect, useRef, useState } from "react";
import logger from "@/app/utils/logger";
import { detectStreamingCodecId, getCodecString } from "@/app/utils/codecConfig";

const useAudioVideoStream = (isUploading: boolean, outputVideo: React.RefObject<HTMLVideoElement | null>) => {
  const mimeCodec = getCodecString("streaming", detectStreamingCodecId());
  const chunks = useRef<Uint8Array[]>([]);
  const mediaSource = useRef<MediaSource | null>(null);
  const mediaSourceBuffer = useRef<SourceBuffer | null>(null);
  const queue = useRef<Uint8Array[]>([]);
  const [noChunks, setNoChunks] = useState(true);

  const cleanUp = () => {
    if (mediaSource.current && mediaSourceBuffer.current) {
      try {
        mediaSource.current.removeSourceBuffer(mediaSourceBuffer.current);
      } catch (error) {
        console.error("Error removing source buffer:", error);
      }
      mediaSource.current = null;
    }

    if (mediaSourceBuffer.current) {
      try {
        if (mediaSourceBuffer.current.updating) {
          mediaSourceBuffer.current.abort();
        }
      } catch (error) {
        console.error("Error aborting source buffer:", error);
      }
      mediaSourceBuffer.current = null;
    }

    chunks.current = [];

    queue.current = [];
  };

  const onStreamEnd = useCallback(() => {
    if (mediaSource.current && mediaSource.current.readyState === "open" && !mediaSourceBuffer.current?.updating) {
      mediaSource.current.endOfStream();

      cleanUp();
    } else {
      mediaSourceBuffer.current?.addEventListener("updateend", function onUpdateEnd() {
        if (mediaSource.current && mediaSource.current.readyState === "open" && !mediaSourceBuffer.current?.updating) {
          mediaSource.current.endOfStream();

          cleanUp();
        }
        mediaSourceBuffer.current?.removeEventListener("updateend", onUpdateEnd);
      });
    }

    // Reset the video element to allow proper seeking with the final file
    if (outputVideo.current) {
      outputVideo.current.src = "";
      outputVideo.current.load();
    }

    setNoChunks(true);
    chunks.current = [];
  }, []);

  const addVideoChunk = (chunkString: string) => {
    if (noChunks) {
      setNoChunks(false);
    }

    const chunk = Uint8Array.from(atob(chunkString), (c) => c.charCodeAt(0));
    chunks.current.push(chunk);

    // Check if media element has an error before appending
    if (outputVideo.current && outputVideo.current.error) {
      logger.error("Media element has error:", outputVideo.current.error);
      return;
    }

    if (
      mediaSource.current &&
      mediaSource.current.readyState === "open" &&
      mediaSourceBuffer.current &&
      !mediaSourceBuffer.current.updating &&
      queue.current.length === 0
    ) {
      try {
        mediaSourceBuffer.current.appendBuffer(chunk);
      } catch (error) {
        logger.error("Error appending buffer:", error);
        // If append fails, add to queue instead
        queue.current.push(chunk);
      }
    } else {
      queue.current.push(chunk);
    }
  };

  useEffect(() => {
    if (!isUploading) {
      return;
    }

    cleanUp();

    setNoChunks(true);
    mediaSource.current = new MediaSource();
    outputVideo.current!.src = URL.createObjectURL(mediaSource.current);

    mediaSource.current.addEventListener("sourceopen", () => {
      if (MediaSource.isTypeSupported(mimeCodec)) {
        if (!mediaSource.current) return;
        const sourceBuffer = mediaSource.current.addSourceBuffer(mimeCodec);

        sourceBuffer.mode = "segments";
        // Handle appending in a queue to avoid errors when buffer is updating
        sourceBuffer.addEventListener("updateend", () => {
          try {
            if (queue.current.length > 0 && !sourceBuffer.updating) {
              const chunk = queue.current.shift();
              if (chunk) {
                sourceBuffer.appendBuffer(chunk as BufferSource);
              }
            }
          } catch (error) {
            logger.error("Error appending buffer:", error);
          }
        });

        mediaSourceBuffer.current = sourceBuffer;
      } else {
        logger.error("MIME type or codec not supported:", mimeCodec);
      }
    });
  }, [isUploading, mimeCodec, outputVideo]);

  return {
    onStreamEnd,
    addVideoChunk,
    noChunks,
  };
};

export default useAudioVideoStream;
