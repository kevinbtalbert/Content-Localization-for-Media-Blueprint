/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { FC } from "react";

const VideoPreviewFooter: FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="flex justify-end text-xs text-gray-400 px-4 py-2 bg-gray-950 gap-2 items-center">{children}</div>
  );
};

export default VideoPreviewFooter;
