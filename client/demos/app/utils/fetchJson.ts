/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

export async function fetchJson<T = unknown>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const contentType = response.headers.get("content-type") || "";
  const bodyText = await response.text();

  if (!contentType.includes("application/json")) {
    const snippet = bodyText.replace(/\s+/g, " ").trim().slice(0, 120);
    throw new Error(
      response.ok
        ? `Expected JSON from ${url} but received ${contentType || "unknown content type"} (${snippet})`
        : `Request to ${url} failed (HTTP ${response.status}): ${snippet || response.statusText}`,
    );
  }

  let data: T;
  try {
    data = JSON.parse(bodyText) as T;
  } catch {
    throw new Error(`Invalid JSON from ${url}: ${bodyText.slice(0, 120)}`);
  }

  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null && "error" in data
        ? String((data as { error?: string }).error)
        : `HTTP ${response.status}`;
    throw new Error(message);
  }

  return data;
}
