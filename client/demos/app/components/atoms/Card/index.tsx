/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { FC, ReactNode } from "react";

const Card: FC<{ children: ReactNode; className?: string; padding?: string }> = ({ children, className, padding }) => {
  return (
    <div
      className={`
    rounded-2xl
    shadow-lg
    ${padding ?? "p-8"}
    border
    border-[color:var(--color-base-border)]
    bg-[color:var(--color-surface-base-background)]
    text-[color:var(--color-primary-foreground)]
    transition
    duration-200
    ${className ?? ""}
  `}
    >
      {children}
    </div>
  );
};

export default Card;
