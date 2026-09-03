/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export type FileTransfer = {
  filename: string;
  direction: "upload" | "download";
  percent: number;
  bytesLoaded: number;
  bytesTotal: number | null;
};

export function transferPercent(loaded: number, total: number | null): number {
  if (!total || total <= 0) {
    return loaded > 0 ? 1 : 0;
  }
  return Math.min(100, Math.round((loaded / total) * 100));
}

function parseContentLength(header: string | null): number | null {
  if (!header) {
    return null;
  }
  const value = Number.parseInt(header, 10);
  return Number.isFinite(value) && value > 0 ? value : null;
}

export async function fetchBlobWithProgress(
  url: string,
  onProgress: (loaded: number, total: number | null) => void,
  init?: RequestInit,
): Promise<Blob> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Download failed (HTTP ${response.status})`);
  }

  const total = parseContentLength(response.headers.get("content-length"));
  const reader = response.body?.getReader();
  if (!reader) {
    const blob = await response.blob();
    onProgress(blob.size, blob.size);
    return blob;
  }

  const chunks: Uint8Array[] = [];
  let loaded = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    chunks.push(value);
    loaded += value.byteLength;
    onProgress(loaded, total);
  }

  return new Blob(chunks, { type: response.headers.get("content-type") || undefined });
}

export async function parseResponseJson<T = unknown>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  const bodyText = await response.text();

  if (!contentType.includes("application/json")) {
    const snippet = bodyText.replace(/\s+/g, " ").trim().slice(0, 120);
    throw new Error(
      response.ok
        ? `Expected JSON but received ${contentType || "unknown content type"} (${snippet})`
        : `Request failed (HTTP ${response.status}): ${snippet || response.statusText}`,
    );
  }

  const data = JSON.parse(bodyText) as T;
  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null && "error" in data
        ? String((data as { error?: string }).error)
        : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

export async function uploadFileWithProgress(
  url: string,
  file: File | Blob,
  filename: string,
  onProgress: (loaded: number, total: number) => void,
  signal?: AbortSignal,
): Promise<Response> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (signal) {
      if (signal.aborted) {
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener(
        "abort",
        () => {
          xhr.abort();
        },
        { once: true },
      );
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded, event.total);
      }
    };

    xhr.onload = () => {
      resolve(
        new Response(xhr.responseText, {
          status: xhr.status,
          statusText: xhr.statusText,
          headers: { "Content-Type": xhr.getResponseHeader("Content-Type") || "application/json" },
        }),
      );
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));

    const formData = new FormData();
    formData.append("file", file, filename);
    xhr.send(formData);
  });
}

export function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
