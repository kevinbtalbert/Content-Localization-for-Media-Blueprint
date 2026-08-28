/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { forwardRef } from "react";

const VideoPreview = forwardRef<HTMLVideoElement, { src?: string; type?: string; footer?: React.ReactNode }>(
  ({ src, type, footer }, ref) => {
    return (
      <div className="rounded-xl overflow-hidden border border-[color:var(--color-base-border)] bg-black mb-4">
        <video ref={ref} controls className="w-full aspect-video bg-black" preload="auto">
          {src && <source src={src} type={type} />}
        </video>
        {footer && <div>{footer}</div>}
      </div>
    );
  },
);

VideoPreview.displayName = "VideoPreview";

export default VideoPreview;
