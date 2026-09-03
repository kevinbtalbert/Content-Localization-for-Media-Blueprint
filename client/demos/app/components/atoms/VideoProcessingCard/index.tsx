/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import Loader from "../Loader";
import ProgressBar from "../ProgressBar";

const VideoProcessingCard: React.FC<{
  showLoader: boolean;
  message: string;
  percent?: number | null;
}> = ({ showLoader, message, percent }) => {
  return (
    <div
      className="flex items-center justify-center bg-[color:var(--color-base-background)] rounded-lg border border-[color:var(--color-base-border)]"
      style={{
        width: "100%",
        aspectRatio: "16/9",
        minHeight: 240,
        maxHeight: 360,
      }}
    >
      <div className="flex w-full max-w-sm flex-col items-center justify-center px-6">
        {showLoader && <Loader />}
        <p className="text-sm text-[color:var(--color-secondary-foreground)]">{message}</p>
        {typeof percent === "number" && (
          <ProgressBar percent={percent} className="mt-4" label={message.replace(/\.\.\.$/, "")} />
        )}
      </div>
    </div>
  );
};

export default VideoProcessingCard;
