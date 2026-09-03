/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import LinkButton from "../atoms/LinkButton";

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
};

type Props = {
  activeFilename: string | null;
  disabled?: boolean;
  onSelect: (entry: VideoLibraryEntry) => void;
  onSampleLoaded: (entry: VideoLibraryEntry) => void;
};

function formatBytes(size: number): string {
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function VideoLibrary({ activeFilename, disabled, onSelect, onSampleLoaded }: Props) {
  const [library, setLibrary] = useState<VideoLibraryState | null>(null);
  const [loadingSample, setLoadingSample] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const loadSampleVideo = async () => {
    setLoadingSample(true);
    setError(null);
    try {
      const response = await fetch("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "load-sample" }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to load sample video");
      }
      const updated = await refresh();
      const entry =
        updated.videos.find((video) => video.filename === data.filename) ||
        ({
          filename: data.filename,
          url: data.url,
          size: 0,
          modified_at: new Date().toISOString(),
          is_sample: true,
        } as VideoLibraryEntry);
      onSampleLoaded(entry);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sample video");
    } finally {
      setLoadingSample(false);
    }
  };

  const selectVideo = async (entry: VideoLibraryEntry) => {
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

  return (
    <div className="mt-4 rounded-xl border border-[color:var(--color-base-border)] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-[color:var(--color-primary-foreground)]">Video library</h3>
        <LinkButton onClick={loadSampleVideo} disabled={disabled || loadingSample}>
          {loadingSample
            ? "Downloading sample…"
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
      ) : library.videos.length === 0 ? (
        <p className="text-xs text-[color:var(--color-secondary-foreground)]">
          No videos yet. Load the NVIDIA sample or upload an MP4.
        </p>
      ) : (
        <ul className="flex max-h-48 flex-col gap-1 overflow-y-auto text-sm">
          {library.videos.map((video) => {
            const isActive = (activeFilename || library.active) === video.filename;
            return (
              <li key={video.filename}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => selectVideo(video)}
                  className={`flex w-full items-center justify-between gap-3 rounded px-2 py-2 text-left transition ${
                    isActive
                      ? "bg-[color:var(--color-interaction-primary-base-background)]/20 text-[color:var(--color-primary-foreground)]"
                      : "hover:bg-[color:var(--color-interaction-hover-background)] text-[color:var(--color-secondary-foreground)]"
                  } ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}
                >
                  <span className="truncate">
                    {video.is_sample ? "Sample: " : ""}
                    {video.filename}
                    {isActive ? " (active)" : ""}
                  </span>
                  <span className="shrink-0 text-xs">{formatBytes(video.size)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
