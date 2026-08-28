/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import { FC } from "react";

const IconCaretDown: FC<{ className?: string }> = ({ className }) => {
  return (
    <svg
      className={`w-4 h-4 text-[color:var(--color-primary-foreground)] transition-transform duration-200 ${className}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  );
};

export default IconCaretDown;
