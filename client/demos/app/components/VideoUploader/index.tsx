/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useConfig } from "@/app/hooks/useConfig";
import Card from "../atoms/Card";
import { H2 } from "../atoms/Text";
import VideoPreview from "../VideoPreview";
import { useState, useEffect, useRef, useCallback } from "react";
import useWebsocket from "@/app/hooks/useWebsocket";
import logger from "@/app/utils/logger";
import ProgressBar from "../atoms/ProgressBar";
import { fetchJson } from "@/app/utils/fetchJson";
import { fetchBlobWithProgress, transferPercent } from "@/app/utils/transferProgress";
import useAudioVideoStream from "@/app/hooks/useAudioVideoStream";
import VideoProcessingCard from "../atoms/VideoProcessingCard";
import useAudioVideoReader from "@/app/hooks/useAudioVideoReader";
import LanguageDropdown from "../atoms/LanguageDropdown";
import Banner, { BannerType } from "../atoms/Banner/Banner";
import VideoPreviewFooter from "../VideoPreviewFooter";
import LinkButton from "../atoms/LinkButton";
import { detectDownloadCodecId, detectStreamingCodecId } from "@/app/utils/codecConfig";
import { useSerializerWorker } from "@/app/hooks/useSerializerWorker";
import AdvancedSettings from "./AdvancedSettings";
import VideoLibrary, { type VideoLibraryEntry, type VideoLibraryHandle } from "./VideoLibrary";
import { PIPELINE_STATUS } from "@/app/api/socketHandlers/content-localization/pipelineStatus";

const MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024; // 1GB in bytes
const MAX_FILE_SIZE_LABEL = "1GB";

const fetchVideoAsFile = async (src: string, filename: string, signal?: AbortSignal): Promise<File> => {
  const response = await fetch(src, { signal });
  const blob = await response.blob();
  return new File([blob], filename, { type: blob.type });
};

const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data URL prefix (e.g., "data:application/json;base64,")
      const base64 = result.split(",")[1];
      resolve(base64);
    };
    reader.onerror = (error) => reject(error);
  });
};

const PIPELINE_STATUS_LABELS: Record<PIPELINE_STATUS, string> = {
  [PIPELINE_STATUS.UPLOADING]: "Uploading",
  [PIPELINE_STATUS.PREPROCESSING]: "Preprocessing",
  [PIPELINE_STATUS.LOCALIZING]: "Localizing",
};

/**
 * Main VideoUploader component that handles video upload, processing, and real-time streaming
 * Manages WebSocket connection to content localization service and audio/video chunk streaming
 */
const VideoUploadContainer = () => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  /** Pipeline status for UI: uploading | preprocessing | localizing */
  const [pipelineStatus, setPipelineStatus] = useState<PIPELINE_STATUS | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inputError, setInputError] = useState<string | null>(null);
  const [diarizationError, setDiarizationError] = useState<string | null>(null);
  /** Chunk streaming progress while sending video to the pipeline (0–100). */
  const [pipelineStreamPercent, setPipelineStreamPercent] = useState<number | null>(null);
  const [outputDownload, setOutputDownload] = useState<{ percent: number; label: string } | null>(null);
  /** Non-fatal preprocessing warning (e.g. voice isolation or diarization failed). */
  const [preprocessingWarning, setPreprocessingWarning] = useState<string | null>(null);
  const [outputFile, setOutputFile] = useState<string | null>(null);
  const {
    loading,
    error: configError,
    sourceLanguages,
    targetLanguages,
    defaultSourceLanguage,
    defaultTargetLanguage,
    enablePreprocessing,
  } = useConfig();
  const [fallbackOutputFile, setFallbackOutputFile] = useState<string | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState<string>(defaultSourceLanguage);
  const [targetLanguage, setTargetLanguage] = useState<string>(defaultTargetLanguage);
  const [voiceIsolation, setVoiceIsolation] = useState<boolean>(false);
  const [diarizationFile, setDiarizationFile] = useState<File | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const outputVideo = useRef<HTMLVideoElement>(null);
  const [hasRunAtLeastOnce, setHasRunAtLeastOnce] = useState(false);
  const { onStreamEnd, addVideoChunk, noChunks } = useAudioVideoStream(isUploading, outputVideo);
  const fileUploadInputRef = useRef<HTMLInputElement>(null);
  const videoLibraryRef = useRef<VideoLibraryHandle>(null);
  const exampleVideoAbortRef = useRef<AbortController | null>(null);
  const [selectedCustomVideo, setSelectedCustomVideo] = useState<string>("");
  const [activeFilename, setActiveFilename] = useState<string | null>(null);
  const [libraryReady, setLibraryReady] = useState(false);
  const videoUploadStartTime = useRef<number>(0);
  const shouldMarkSocketError = useRef(false);
  const indexRef = useRef(0);
  const totalPacketsRef = useRef(0);
  const ended = useRef(false);

  const { startAudioVideoReader, stopAudioVideoReader } = useAudioVideoReader();

  // WebSocket connection for real-time communication with content localization service
  const ws = useWebsocket("/api/ws/content-localization", {
    open: () => {
      logger.info("Connected to the websocket server");
    },
    message: (event) => {
      const data = JSON.parse(event.data);
      logger.debug("Received message from the websocket server: %s", data.type);

      if (data.type === "translate") {
        // Handle completion of video processing pipeline
        logger.info(`Pipeline completed in ${Date.now() - videoUploadStartTime.current}ms`);
        videoUploadStartTime.current = 0;
        shouldMarkSocketError.current = false;
        setPipelineStatus(null);
        if (data.data.error) {
          setError(data.data.error);
          setIsUploading(false);
        } else {
          logger.info("Output video file path: ", data.data.outputVideo);
          setOutputFile(data.data.outputVideo);
          setFallbackOutputFile(data.data.fallbackOutputVideo);
          setIsUploading(false);
        }
        onStreamEnd();

        // Disconnect from websocket after processing is complete
        ws.disconnect();
        logger.info("Disconnected from websocket server after processing completion");
      } else if (data.type === "status" && data.data?.status) {
        setPipelineStatus(data.data.status);
      } else if (data.type === "warning" && data.data?.message) {
        // Non-fatal preprocessing warning (voice isolation or diarization failed)
        setPreprocessingWarning(data.data.message);
      } else if (data.type === "video_chunk") {
        // Stream video chunks for real-time preview during processing
        addVideoChunk(data.data.chunk);
      }
    },
    error: (event) => {
      logger.error("Websocket error: ", event);
      handleWebsocketError();
    },
  });

  const connected = ws.status === "open";

  const handleWebsocketError = useCallback(
    (message?: string) => {
      logger.info("Websocket is disconnected, stopping audio video reader, error: ", message);
      stopAudioVideoReader();
      setIsUploading(false);
      setError(message || "Connection with backend disconnected, please try again.");
      onStreamEnd();
    },
    [stopAudioVideoReader, onStreamEnd],
  );

  const onSerialized = useCallback(
    async (message: string, index: number) => {
      if (ws.socket && message) {
        logger.debug(`Sending message to websocket: ${index}`);
        ws.socket.send(message);
      }

      if (totalPacketsRef.current > 0) {
        setPipelineStreamPercent(transferPercent(index, totalPacketsRef.current));
      }

      if (ended.current && index >= totalPacketsRef.current) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        logger.info(`Ended and ${index} >= ${totalPacketsRef.current}, stopping audio video reader`);
        stopAudioVideoReader();

        if (connected) {
          try {
            ws.sendJSON({ type: "data_end" });
          } catch (error) {
            logger.error("Failed to send chunk end signal:", error);
            handleWebsocketError();
          }
        } else {
          logger.warn("Websocket not connected, cannot send chunk end signal");
        }
      }

      if (index % 100 === 0) {
        logger.debug(`Sent chunk: ${index}`);
      }
    },
    [ws.socket, ws.sendJSON, connected, stopAudioVideoReader, handleWebsocketError],
  );

  const onSerializerError = useCallback(
    (error: string) => {
      logger.error("Worker serialization error:", error);
      handleWebsocketError(error);
    },
    [handleWebsocketError],
  );

  const { serializeChunk } = useSerializerWorker(onSerialized, onSerializerError);

  /** Load a library video into preview state and processing file handle. */
  const loadVideoFromEntry = useCallback(
    async (entry: Pick<VideoLibraryEntry, "url" | "filename">, signal?: AbortSignal): Promise<File | null> => {
      exampleVideoAbortRef.current?.abort();
      const controller = signal ? null : new AbortController();
      const abortSignal = signal ?? controller!.signal;
      if (controller) {
        exampleVideoAbortRef.current = controller;
      }

      setSelectedCustomVideo(entry.url);
      setActiveFilename(entry.filename);
      if (videoRef.current) {
        videoRef.current.src = entry.url;
        videoRef.current.load();
      }

      try {
        const videoFile = await fetchVideoAsFile(entry.url, entry.filename, abortSignal);
        setFile(videoFile);
        setInputError(null);
        return videoFile;
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return null;
        }
        logger.error("Failed to load video from library:", error);
        setInputError("Failed to load the selected video.");
        return null;
      }
    },
    [],
  );

  // Update language states when defaults are loaded
  useEffect(() => {
    if (!loading && defaultSourceLanguage && defaultTargetLanguage) {
      setSourceLanguage(defaultSourceLanguage);
      setTargetLanguage(defaultTargetLanguage);
    }
  }, [defaultSourceLanguage, defaultTargetLanguage, loading]);

  // Restore the persisted active video from the server-side /videos library.
  useEffect(() => {
    const controller = new AbortController();
    exampleVideoAbortRef.current = controller;

    const restoreActiveVideo = async () => {
      try {
        const data = await fetchJson<{
          videos: VideoLibraryEntry[];
          active: string | null;
        }>("/api/media", { signal: controller.signal, cache: "no-store" });
        setLibraryReady(true);
        if (!data.active) {
          return;
        }
        const entry =
          (data.videos as VideoLibraryEntry[]).find((video) => video.filename === data.active) ||
          ({
            filename: data.active,
            url: `/api/media/${encodeURIComponent(data.active)}`,
          } as VideoLibraryEntry);
        await loadVideoFromEntry(entry, controller.signal);
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        logger.error("Failed to restore active video:", error);
        setLibraryReady(true);
      }
    };

    void restoreActiveVideo();

    return () => {
      controller.abort();
      exampleVideoAbortRef.current = null;
    };
  }, [loadVideoFromEntry]);

  // Cleanup websocket connection on component unmount
  useEffect(() => {
    return () => {
      ws.disconnect();
      stopAudioVideoReader();
      logger.info("Disconnected from websocket server and stopped audio video reader on component unmount");
    };
  }, []);

  /**
   * Callback for processing audio/video chunks from the reader
   * Sends chunks to Web Worker for serialization - no main thread blocking!
   */
  const onAudioVideoData = useCallback(
    async (audio: ArrayBuffer, video?: ArrayBuffer) => {
      indexRef.current++;
      // Send to worker - serialization and JSON.stringify happens in separate thread
      serializeChunk(audio, video, indexRef.current);
    },
    [serializeChunk],
  );

  /**
   * Callback when audio/video streaming ends
   * Sends end signal to server and stops the reader
   */
  const onAudioVideoEnd = useCallback(
    async (totalPackets: number) => {
      totalPacketsRef.current = totalPackets;
      ended.current = true;
      // ws is intentionally omitted to prevent infinite re-renders since ws.sendJSON recreates on socket changes
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [stopAudioVideoReader, connected, handleWebsocketError],
  );

  const onAudioVideoProgress = useCallback((sentChunks: number, totalChunks: number) => {
    setPipelineStreamPercent(transferPercent(sentChunks, totalChunks));
  }, []);

  const onAudioVideoError = useCallback(
    (error: string) => {
      logger.error("Audio/video reader error:", error);
      setInputError(error);
      setIsUploading(false);
      onStreamEnd();
      ws.disconnect();
    },
    [onStreamEnd],
  );

  // Monitor WebSocket connection status and handle errors during upload
  useEffect(() => {
    if (!connected && isUploading && shouldMarkSocketError.current) {
      handleWebsocketError();
    }
  }, [connected, isUploading, handleWebsocketError]);

  /**
   * Sends language configuration to the server once
   */
  const sendLanguageConfig = useCallback(async () => {
    if (connected) {
      try {
        const streamingCodecId = detectStreamingCodecId();
        const downloadCodecId = detectDownloadCodecId();

        logger.info("Sending language configuration:", {
          sourceLanguage,
          targetLanguage,
          streamingCodecId,
          downloadCodecId,
        });

        const diarizationFileBase64 = diarizationFile ? await fileToBase64(diarizationFile) : null;

        ws.sendJSON({
          type: "localization_configs",
          data: {
            source_language: sourceLanguage,
            target_language: targetLanguage,
            streaming_codec_id: streamingCodecId,
            download_codec_id: downloadCodecId,
            voice_isolation: voiceIsolation,
            diarization_file: diarizationFileBase64,
          },
        });
      } catch (error) {
        logger.error("Failed to send language configuration:", error);
      }
    }
    // ws is intentionally omitted to prevent infinite re-renders since ws.sendJSON recreates on socket changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, sourceLanguage, targetLanguage, voiceIsolation, diarizationFile]);

  // Start audio/video processing when file is selected and WebSocket is connected
  useEffect(() => {
    if (file && connected) {
      logger.info("Websocket is connected, starting audio video reader");
      ended.current = false;
      totalPacketsRef.current = 0;
      indexRef.current = 0;
      sendLanguageConfig();
      startAudioVideoReader(
        file,
        onAudioVideoData,
        onAudioVideoEnd,
        onAudioVideoError,
        onAudioVideoProgress,
      );
      shouldMarkSocketError.current = true;
    }
    // Callbacks are intentionally omitted to prevent restarting audio/video processing
    // when callback dependencies change. The callbacks access current values via closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, file]);

  /**
   * Initiates video processing pipeline
   * Connects to WebSocket and starts streaming audio/video chunks
   */
  const handleUpload = async () => {
    if (!file) return;

    setHasRunAtLeastOnce(true);
    shouldMarkSocketError.current = false;

    setIsUploading(true);
    setPipelineStatus(null);
    setPipelineStreamPercent(null);
    setError(null);
    setPreprocessingWarning(null);
    setOutputFile(null);

    logger.info("File details:", {
      name: file.name,
      type: file.type,
      size: file.size,
      lastModified: file.lastModified,
    });

    videoUploadStartTime.current = Date.now();

    logger.info("Connecting to websocket server for video processing");
    const socket = await ws.connect();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setIsUploading(false);
      setError("Could not connect to the processing pipeline. Check that the demo app is running and try again.");
      onStreamEnd();
      return;
    }
  };

  /**
   * Handles file selection from input element
   * Validates file type and sets up video preview
   */
  const onFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];

    setInputError(null);

    if (selected && selected.type !== "video/mp4") {
      setInputError("Please upload an MP4 video file.");
      e.target.value = "";
      return;
    }
    if (selected && selected.size > MAX_FILE_SIZE) {
      setInputError(`File size should not exceed ${MAX_FILE_SIZE_LABEL}.`);
      e.target.value = "";
      return;
    }
    if (!selected) {
      return;
    }

    try {
      const entry = await videoLibraryRef.current?.uploadFile(selected);
      if (!entry) {
        return;
      }
      await loadVideoFromEntry({ url: entry.url, filename: entry.filename });
    } catch (error) {
      setInputError(error instanceof Error ? error.message : "Failed to upload video");
      e.target.value = "";
    }
  };

  /**
   * Resets component state to initial values
   * Disconnects WebSocket and loads default example video
   */
  const handleReset = async () => {
    setError(null);
    setPreprocessingWarning(null);
    setOutputFile(null);
    setPipelineStatus(null);
    setPipelineStreamPercent(null);
    setOutputDownload(null);
    setIsUploading(false);
    setHasRunAtLeastOnce(false);
    setSourceLanguage(defaultSourceLanguage);
    setTargetLanguage(defaultTargetLanguage);
    setVoiceIsolation(false);
    setDiarizationFile(null);
    setDiarizationError(null);
    if (fileUploadInputRef.current) {
      fileUploadInputRef.current.value = "";
    }
    setInputError(null);

    stopAudioVideoReader();
    ws.disconnect();
    logger.info("Disconnected from websocket server on reset");

    try {
      const data = await fetchJson<{ active: string | null; videos: VideoLibraryEntry[] }>("/api/media", {
        cache: "no-store",
      });
      if (data.active) {
        const entry =
          (data.videos as VideoLibraryEntry[]).find((video) => video.filename === data.active) ||
          ({
            filename: data.active,
            url: `/api/media/${encodeURIComponent(data.active)}`,
          } as VideoLibraryEntry);
        await loadVideoFromEntry(entry);
        return;
      }
    } catch (error) {
      logger.error("Failed to restore active video on reset:", error);
    }

    setFile(null);
    setActiveFilename(null);
    setSelectedCustomVideo("");
    if (videoRef.current) {
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
  };

  const handleDownload = async (fileUrl: string, downloadLabel?: string) => {
    if (!fileUrl) {
      return;
    }
    const filename = fileUrl.split("/").pop() || `output.${detectDownloadCodecId() === "default" ? "mp4" : "webm"}`;
    const label = downloadLabel || `Downloading ${filename}`;
    setOutputDownload({ percent: 0, label });
    try {
      const blob = await fetchBlobWithProgress(fileUrl, (loaded, total) => {
        setOutputDownload({ percent: transferPercent(loaded, total), label });
      });
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch (error) {
      logger.error("Download failed:", error);
      setError(error instanceof Error ? error.message : "Download failed");
    } finally {
      setOutputDownload(null);
    }
  };

  const processingPercent =
    pipelineStatus === PIPELINE_STATUS.UPLOADING || pipelineStreamPercent != null
      ? pipelineStreamPercent
      : null;

  return (
    <div className="flex flex-col gap-8">
      <Card>
        <Banner type={BannerType.Info}>
          AI models generate responses and outputs based on complex algorithms and machine learning techniques, and
          those responses or outputs may be inaccurate, harmful, biased or indecent. By testing this model, you assume
          the risk of any harm caused by any response or output of the model.
        </Banner>

        <div className="grid grid-cols-1 md:grid-cols-2 mt-4 max-md:mt-8">
          {/* Input Video Card */}
          <div className="pr-8 md:pt-8 border-r max-md:border-r-0 max-md:border-b max-md:pb-8 max-md:pr-0 border-[color:var(--color-base-border)]">
            <div className="flex items-center justify-between mb-4 md:mb-8 md:pb-[8px] md:border-b border-[color:var(--color-base-border)]">
              <H2>Input</H2>
            </div>
            <VideoPreview
              src={selectedCustomVideo}
              ref={videoRef}
              footer={
                <VideoPreviewFooter>
                  <span>File Types: .mp4</span>
                  <input
                    type="file"
                    className="hidden"
                    ref={fileUploadInputRef}
                    onChange={onFileSelected}
                    accept=".mp4"
                  ></input>
                  <LinkButton onClick={() => fileUploadInputRef.current?.click()}>Upload New Video</LinkButton>
                </VideoPreviewFooter>
              }
            />
            {inputError && <Banner type={BannerType.Error}>{inputError}</Banner>}

            <VideoLibrary
              ref={videoLibraryRef}
              activeFilename={activeFilename}
              disabled={isUploading}
              onSelect={(entry) => {
                void loadVideoFromEntry(entry);
              }}
              onSampleLoaded={(entry) => {
                void loadVideoFromEntry(entry);
              }}
            />

            {!libraryReady && !file && (
              <p className="mt-2 text-xs text-[color:var(--color-secondary-foreground)]">
                Loading saved videos…
              </p>
            )}

            {/* Action Buttons */}
            <div className="flex gap-2 mt-4 justify-end">
              <button
                className="px-4 py-2 rounded-md text-sm font-semibold bg-transparent border 
                    border-[color:var(--color-interaction-base-border)] 
                    text-[color:var(--color-primary-foreground)] 
                    hover:bg-[color:var(--color-interaction-hover-background)] 
                    focus:outline-none focus:ring-2 focus:ring-offset-2 
                    focus:ring-[color:var(--color-brand-border)] 
                    cursor-pointer"
                onClick={handleReset}
              >
                Reset
              </button>
              <button
                disabled={isUploading || !file || file.size === 0}
                className={`px-4 py-2 rounded-md text-sm font-semibold
                    ${
                      isUploading || !file || file.size === 0
                        ? "bg-[color:var(--color-base-border)] text-[color:var(--color-subtle-foreground)] cursor-not-allowed"
                        : "bg-[color:var(--color-interaction-primary-base-background)] text-black hover:bg-[color:var(--color-interaction-primary-hover-background)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[color:var(--color-brand-border)] cursor-pointer"
                    }`}
                onClick={handleUpload}
              >
                {isUploading ? "Processing..." : "Run"}
              </button>
            </div>

            {/* Language Selection */}
            <div className="mt-4">
              <div className="rounded-xl border border-[color:var(--color-base-border)] p-4">
                <H2 className="text-2xl font-semibold text-[color:var(--color-primary-foreground)] tracking-tight mb-[8px]">
                  Configs
                </H2>
                {loading ? (
                  <div className="text-sm text-[color:var(--color-secondary-foreground)]">Loading configs...</div>
                ) : configError ? (
                  <div className="text-sm text-[color:var(--color-feedback-danger-foreground)]">
                    Error loading configs: {configError}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-4">
                    <LanguageDropdown
                      label="Source Language"
                      value={sourceLanguage}
                      onChange={setSourceLanguage}
                      disabled={isUploading}
                      excludeLanguage={targetLanguage}
                      languages={sourceLanguages}
                    />
                    <LanguageDropdown
                      label="Target Language"
                      value={targetLanguage}
                      onChange={setTargetLanguage}
                      disabled={isUploading}
                      excludeLanguage={sourceLanguage}
                      languages={targetLanguages}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Advanced Settings: only when preprocessing is enabled (e.g. ElevenLabs backend) */}
            {enablePreprocessing && (
              <AdvancedSettings
                voiceIsolation={voiceIsolation}
                onVoiceIsolationChange={setVoiceIsolation}
                diarizationFile={diarizationFile}
                onDiarizationFileChange={setDiarizationFile}
                diarizationError={diarizationError}
                onDiarizationErrorChange={setDiarizationError}
                disabled={isUploading}
              />
            )}
          </div>

          {/* Output Video Card */}
          <div className="pl-8 pt-8 max-md:pl-0 max-md:pt-8">
            <div className="flex items-center justify-between mb-4 md:mb-8 md:pb-[8px] md:border-b border-[color:var(--color-base-border)]">
              <H2>Output</H2>
              {isUploading && pipelineStatus && (
                <div className="text-sm text-[color:var(--color-feedback-success-foreground)]">
                  {PIPELINE_STATUS_LABELS[pipelineStatus]}
                </div>
              )}
            </div>

            {/* Error Display */}
            {error && <Banner type={BannerType.Error}>{error || "Something went wrong. Please try again."}</Banner>}

            {/* Real-time Processing Video Preview */}
            {!error && !outputFile && isUploading && (
              <video
                className="in-progress-video rounded-xl overflow-hidden border border-[color:var(--color-base-border)] bg-black mb-4"
                key="in-progress-video"
                ref={outputVideo}
                style={
                  noChunks
                    ? {
                        display: "none",
                      }
                    : {}
                }
                controls
              />
            )}

            {/* Final Processed Video */}
            {!isUploading && outputFile && !error && (
              <VideoPreview
                key="final-video"
                src={detectDownloadCodecId() === "fallback" && fallbackOutputFile ? fallbackOutputFile : outputFile}
                footer={
                  <VideoPreviewFooter>
                    <LinkButton onClick={() => handleDownload(outputFile)}>Download</LinkButton>
                    {detectDownloadCodecId() === "fallback" && fallbackOutputFile && (
                      <LinkButton variant="secondary" onClick={() => handleDownload(fallbackOutputFile, "Downloading WebM…")}>
                        Download WebM (Safari compatible)
                      </LinkButton>
                    )}
                  </VideoPreviewFooter>
                }
              />
            )}

            {outputDownload && (
              <div className="mt-4">
                <ProgressBar percent={outputDownload.percent} label={outputDownload.label} />
              </div>
            )}

            {/* Processing Status Indicators */}
            {noChunks && isUploading && (
              <VideoProcessingCard
                showLoader={true}
                message={pipelineStatus ? `${PIPELINE_STATUS_LABELS[pipelineStatus]}...` : "Processing..."}
                percent={processingPercent}
              />
            )}

            {!hasRunAtLeastOnce && <VideoProcessingCard showLoader={false} message="Press Run to start processing" />}

            {/* Preprocessing warning */}
            {preprocessingWarning && (
              <div className="mt-4">
                <Banner type={BannerType.Warning}>{preprocessingWarning}</Banner>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default VideoUploadContainer;
