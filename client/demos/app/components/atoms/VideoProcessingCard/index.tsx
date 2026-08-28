/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import Loader from "../Loader";

const VideoProcessingCard: React.FC<{ showLoader: boolean; message: string }> = ({ showLoader, message }) => {
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
      <div className="flex flex-col items-center justify-center">
        {showLoader && <Loader />}
        <p className="text-sm text-[color:var(--color-secondary-foreground)]">{message}</p>
      </div>
    </div>
  );
};

export default VideoProcessingCard;
