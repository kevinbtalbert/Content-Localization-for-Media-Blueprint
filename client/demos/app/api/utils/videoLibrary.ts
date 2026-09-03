/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

/** @deprecated Use mediaLibrary.ts — kept for backwards-compatible Next.js route stubs. */
export * from "./mediaLibrary";

export {
  listMedia as listVideos,
  mediaDir as videosDir,
  mediaFilePath as videoFilePath,
  saveUploadedMedia as saveUploadedVideo,
  type MediaEntry as VideoEntry,
} from "./mediaLibrary";
