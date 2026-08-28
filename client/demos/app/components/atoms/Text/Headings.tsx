/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { FC } from "react";

export const H2: FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => {
  return <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>;
};
