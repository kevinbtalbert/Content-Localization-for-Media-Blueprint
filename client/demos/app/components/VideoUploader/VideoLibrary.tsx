/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import LinkButton from "../atoms/LinkButton";
import ProgressBar from "../atoms/ProgressBar";
import { SAMPLE_VIDEO_FILENAME, SAMPLE_VIDEO_URL } from "@/app/constants/videoLibrary";
import {
  type FileTransfer,
  fetchBlobWithProgress,
  formatBytes,
  transferPercent,
  uploadFileWithProgress,
} from "@/app/utils/transferProgress";

export type VideoLibraryEntry = {
  filename: string;
  size: number;
  modified_at: string;
  url: string;
  is_sample: boolean;
};

type VideoLibraryState = {
  videos: VideoLibraryEntry[];
  active: string | null;
  sample_cached: boolean;
  sample_url?: string;
  sample_filename?: string;
};

export type VideoLibraryHandle = {
  uploadFile: (file: File) => Promise<VideoLibraryEntry | null>;
};

type Props = {
  activeFilename: string | null;
  disabled?: boolean;
  onSelect: (entry: VideoLibraryEntry) => void;
  onSampleLoaded: (entry: VideoLibraryEntry) => void;
};

type DisplayEntry = VideoLibraryEntry & {
  transfer?: FileTransfer;
};

function mergeLibraryEntries(videos: VideoLibraryEntry[], transfers: Record<string, FileTransfer>): DisplayEntry[] {
  const byName = new Map<string, DisplayEntry>();

  for (const video of videos) {
    byName.set(video.filename, { ...video, transfer: transfers[video.filename] });
  }

  for (const transfer of Object.values(transfers)) {
    if (!byName.has(transfer.filename)) {
      byName.set(transfer.filename, {
        filename: transfer.filename,
        size: transfer.bytesTotal ?? transfer.bytesLoaded,
        modified_at: new Date().toISOString(),
        url: `/api/videos/${encodeURIComponent(transfer.filename)}`,
        is_sample: transfer.filename === SAMPLE_VIDEO_FILENAME,
        transfer,
      });
    }
  }

  return Array.from(byName.values()).sort((a, b) => {
    if (a.transfer && !b.transfer) {
      return -1;
    }
    if (!a.transfer && b.transfer) {
      return 1;
    }
    return b.modified_at.localeCompare(a.modified_at);
  });
}

function transferLabel(transfer: FileTransfer): string {
  const verb = transfer.direction === "download" ? "Downloading" : "Uploading";
  const size =
    transfer.bytesTotal != null
      ? `${formatBytes(transfer.bytesLoaded)} / ${formatBytes(transfer.bytesTotal)}`
      : formatBytes(transfer.bytesLoaded);
  return `${verb} · ${size}`;
}

const VideoLibrary = forwardRef<VideoLibraryHandle, Props>(function VideoLibrary(
  { activeFilename, disabled, onSelect, onSampleLoaded },
  ref,
) {
  const [library, setLibrary] = useState<VideoLibraryState | null>(null);
  const [transfers, setTransfers] = useState<Record<string, FileTransfer>>({});
  const [error, setError] = useState<string | null>(null);
  const transferAbortRef = useRef<AbortController | null>(null);

  const updateTransfer = useCallback((filename: string, patch: Partial<FileTransfer> | null) => {
    setTransfers((current) => {
      if (patch === null) {
        if (!(filename in current)) {
          return current;
        }
        const next = { ...current };
        delete next[filename];
        return next;
      }
      const existing = current[filename];
      const nextEntry: FileTransfer = {
        filename,
        direction: patch.direction ?? existing?.direction ?? "upload",
        bytesLoaded: patch.bytesLoaded ?? existing?.bytesLoaded ?? 0,
        bytesTotal: patch.bytesTotal !== undefined ? patch.bytesTotal : (existing?.bytesTotal ?? null),
        percent: patch.percent ?? existing?.percent ?? 0,
      };
      return { ...current, [filename]: nextEntry };
    });
  }, []);

  const refresh = useCallback(async () => {
    const response = await fetch("/api/videos", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to load video library");
    }
    setLibrary(data as VideoLibraryState);
    return data as VideoLibraryState;
  }, []);

  useEffect(() => {
    refresh().catch((err) => {
      setError(err instanceof Error ? err.message : "Failed to load video library");
    });
  }, [refresh]);

  const uploadFile = useCallback(
    async (file: File): Promise<VideoLibraryEntry | null> => {
      transferAbortRef.current?.abort();
      const controller = new AbortController();
      transferAbortRef.current = controller;

      setError(null);
      updateTransfer(file.name, {
        direction: "upload",
        percent: 0,
        bytesLoaded: 0,
        bytesTotal: file.size,
      });

      try {
        const response = await uploadFileWithProgress(
          "/api/videos",
          file,
          file.name,
          (loaded, total) => {
            updateTransfer(file.name, {
              direction: "upload",
              bytesLoaded: loaded,
              bytesTotal: total,
              percent: transferPercent(loaded, total),
            });
          },
          controller.signal,
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Failed to upload video");
        }

        updateTransfer(file.name, null);
        const updated = await refresh();
        const entry =
          updated.videos.find((video) => video.filename === data.filename) ||
          ({
            filename: data.filename,
            url: data.url,
            size: file.size,
            modified_at: new Date().toISOString(),
            is_sample: false,
          } as VideoLibraryEntry);
        return entry;
      } catch (err) {
        updateTransfer(file.name, null);
        if (err instanceof Error && err.name === "AbortError") {
          return null;
        }
        throw err;
      }
    },
    [refresh, updateTransfer],
  );

  useImperativeHandle(ref, () => ({ uploadFile }), [uploadFile]);

  const loadSampleVideo = async () => {
    transferAbortRef.current?.abort();
    const controller = new AbortController();
    transferAbortRef.current = controller;

    setError(null);

    const sampleUrl = library?.sample_url || SAMPLE_VIDEO_URL;
    const sampleFilename = library?.sample_filename || SAMPLE_VIDEO_FILENAME;

    if (library?.sample_cached) {
      try {
        const updated = await refresh();
        const entry = updated.videos.find((video) => video.filename === sampleFilename);
        if (entry) {
          onSampleLoaded(entry);
          return;
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load sample video");
        return;
      }
    }

    try {
      updateTransfer(sampleFilename, {
        direction: "download",
        percent: 0,
        bytesLoaded: 0,
        bytesTotal: null,
      });

      const blob = await fetchBlobWithProgress(
        sampleUrl,
        (loaded, total) => {
          updateTransfer(sampleFilename, {
            direction: "download",
            bytesLoaded: loaded,
            bytesTotal: total,
            percent: transferPercent(loaded, total),
          });
        },
        { signal: controller.signal },
      );

      const sampleFile = new File([blob], sampleFilename, { type: blob.type || "video/mp4" });
      updateTransfer(sampleFilename, {
        direction: "upload",
        percent: 0,
        bytesLoaded: 0,
        bytesTotal: sampleFile.size,
      });

      const response = await uploadFileWithProgress(
        "/api/videos",
        sampleFile,
        sampleFilename,
        (loaded, total) => {
          updateTransfer(sampleFilename, {
            direction: "upload",
            bytesLoaded: loaded,
            bytesTotal: total,
            percent: transferPercent(loaded, total),
          });
        },
        controller.signal,
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to save sample video");
      }

      updateTransfer(sampleFilename, null);
      const updated = await refresh();
      const entry =
        updated.videos.find((video) => video.filename === data.filename) ||
        ({
          filename: data.filename,
          url: data.url,
          size: sampleFile.size,
          modified_at: new Date().toISOString(),
          is_sample: true,
        } as VideoLibraryEntry);
      onSampleLoaded(entry);
    } catch (err) {
      updateTransfer(sampleFilename, null);
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load sample video");
    }
  };

  const selectVideo = async (entry: VideoLibraryEntry) => {
    if (transfers[entry.filename]) {
      return;
    }
    setError(null);
    try {
      const response = await fetch("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "select", filename: entry.filename }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to select video");
      }
      await refresh();
      onSelect(entry);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to select video");
    }
  };

  const displayEntries = useMemo(
    () => mergeLibraryEntries(library?.videos ?? [], transfers),
    [library?.videos, transfers],
  );

  const sampleTransfer = transfers[SAMPLE_VIDEO_FILENAME];
  const loadingSample = Boolean(sampleTransfer);

  return (
    <div className="mt-4 rounded-xl border border-[color:var(--color-base-border)] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-[color:var(--color-primary-foreground)]">Video library</h3>
        <LinkButton onClick={loadSampleVideo} disabled={disabled || loadingSample}>
          {loadingSample
            ? sampleTransfer?.direction === "download"
              ? "Downloading sample…"
              : "Saving sample…"
            : library?.sample_cached
              ? "Reload sample video"
              : "Load sample video"}
        </LinkButton>
      </div>
      <p className="mb-3 text-xs text-[color:var(--color-secondary-foreground)]">
        Videos are stored in the project <code className="text-[color:var(--color-primary-foreground)]">/videos</code>{" "}
        folder. The active video is remembered until you upload or select another.
      </p>
      {error && <p className="mb-2 text-xs text-[color:var(--color-feedback-danger-foreground)]">{error}</p>}
      {!library ? (
        <p className="text-xs text-[color:var(--color-secondary-foreground)]">Loading library…</p>
      ) : displayEntries.length === 0 ? (
        <p className="text-xs text-[color:var(--color-secondary-foreground)]">
          No videos yet. Load the NVIDIA sample or upload an MP4.
        </p>
      ) : (
        <ul className="flex max-h-56 flex-col gap-2 overflow-y-auto text-sm">
          {displayEntries.map((video) => {
            const isActive = (activeFilename || library.active) === video.filename;
            const transfer = video.transfer;
            const isBusy = Boolean(transfer);
            return (
              <li
                key={video.filename}
                className={`rounded border px-2 py-2 ${
                  isActive
                    ? "border-[color:var(--color-interaction-primary-base-background)]/40 bg-[color:var(--color-interaction-primary-base-background)]/10"
                    : "border-transparent"
                }`}
              >
                <button
                  type="button"
                  disabled={disabled || isBusy}
                  onClick={() => selectVideo(video)}
                  className={`flex w-full items-center justify-between gap-3 text-left transition ${
                    isActive
                      ? "text-[color:var(--color-primary-foreground)]"
                      : "text-[color:var(--color-secondary-foreground)]"
                  } ${disabled || isBusy ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:text-[color:var(--color-primary-foreground)]"}`}
                >
                  <span className="truncate">
                    {video.is_sample ? "Sample: " : ""}
                    {video.filename}
                    {isActive ? " (active)" : ""}
                  </span>
                  <span className="shrink-0 text-xs">
                    {transfer ? `${transfer.percent}%` : formatBytes(video.size)}
                  </span>
                </button>
                {transfer && (
                  <ProgressBar
                    className="mt-2"
                    percent={transfer.percent}
                    label={transferLabel(transfer)}
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
});

export default VideoLibrary;
